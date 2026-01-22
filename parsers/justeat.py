import re
from datetime import datetime
from typing import Optional
from bs4 import BeautifulSoup
from .base import Platform, ParsedOrder, ParsedInvoice, parse_european_number


def parse_justeat_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%d/%m/%Y")
    except ValueError:
        return None


def parse_justeat_invoice(filepath: str) -> ParsedInvoice:
    result = ParsedInvoice(
        platform=Platform.JUSTEAT,
        filename=filepath,
        parse_date=datetime.now()
    )

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(filepath, 'r', encoding='iso-8859-1') as f:
                content = f.read()
        except Exception as e:
            result.errors.append(f"Failed to read file: {e}")
            return result
    except Exception as e:
        result.errors.append(f"Failed to read file: {e}")
        return result

    soup = BeautifulSoup(content, 'html.parser')

    # Extract restaurant name and ID
    for td in soup.find_all('td'):
        text = td.get_text()
        if 'ID Ristorante:' in text:
            result.restaurant_name = text.split('ID Ristorante:')[0].strip().split('\n')[0].strip()
            id_match = re.search(r'ID Ristorante:\s*(\d+)', text)
            if id_match:
                result.restaurant_id = id_match.group(1)
            break

    # Extract summary data
    for td in soup.find_all('td'):
        text = td.get_text()
        if 'Riceverai da JUST EAT' in text:
            amount_match = re.search(r'€\s*([\d.,]+)', text)
            if amount_match:
                result.summary_net_payout = parse_european_number(amount_match.group(1))
        elif 'Numero di ordini' in text:
            num_match = re.search(r'(\d+)', text.split('Numero di ordini')[-1])
            if num_match:
                result.summary_total_orders = int(num_match.group(1))
        elif 'Vendite totali' in text:
            amount_match = re.search(r'€\s*([\d.,]+)', text)
            if amount_match:
                result.summary_gross_sales = parse_european_number(amount_match.group(1))

    # Extract fees
    fee_patterns = [
        (r'Commissione di Just-Eat', 'commission'),
        (r'Top Rank', 'top_rank'),
        (r'Spese di amministrazione', 'admin_fee'),
        (r'Tariffe per l\'attesa', 'wait_time_fee'),
    ]

    for tr in soup.find_all('tr'):
        cells = tr.find_all('td')
        if len(cells) >= 2:
            text = cells[0].get_text()
            for pattern, fee_type in fee_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    amount_text = cells[-1].get_text()
                    amount_match = re.search(r'€\s*([\d.,]+)', amount_text)
                    if amount_match:
                        result.fees.append({
                            'type': fee_type,
                            'description': text.strip()[:100],
                            'amount': parse_european_number(amount_match.group(1)),
                            'date': result.parse_date
                        })

    # Extract orders
    for table in soup.find_all('table'):
        headers = table.find_all('th')
        header_text = ' '.join([h.get_text() for h in headers])
        if 'Num. ordine' in header_text:
            for row in table.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 7:
                    first_cell = cells[0].get_text().strip()
                    if not first_cell.isdigit():
                        continue

                    date_str = cells[1].get_text().strip()
                    order_num = cells[2].get_text().strip()
                    order_type_text = cells[3].get_text().strip()
                    cash_text = cells[4].get_text().strip()
                    card_text = cells[5].get_text().strip()
                    total_text = cells[6].get_text().strip()

                    cash_match = re.search(r'€\s*([\d.,]+)', cash_text)
                    cash_amount = parse_european_number(cash_match.group(1)) if cash_match else 0.0

                    card_match = re.search(r'€\s*([\d.,]+)', card_text)
                    card_amount = parse_european_number(card_match.group(1)) if card_match else 0.0

                    total_match = re.search(r'€\s*([\d.,]+)', total_text)
                    total_amount = parse_european_number(total_match.group(1)) if total_match else 0.0

                    is_pickup = 'Asporto' in order_type_text or 'Ritir' in order_type_text

                    order = ParsedOrder(
                        platform=Platform.JUSTEAT,
                        order_id=order_num,
                        order_number=order_num,
                        restaurant_name=result.restaurant_name,
                        restaurant_address='',
                        restaurant_id=result.restaurant_id,
                        order_datetime=parse_justeat_date(date_str),
                        gross_value=total_amount,
                        commission_amount=0.0,
                        commission_rate=0.0,
                        vat_amount=0.0,
                        net_payout=0.0,
                        is_cash_order=cash_amount > 0,
                        cash_payment_adjustment=cash_amount,
                        order_type="pickup" if is_pickup else "delivery"
                    )
                    result.orders.append(order)
            break

    # Distribute commission proportionally
    total_commission = sum(f['amount'] for f in result.fees if f['type'] == 'commission')
    total_gross = sum(o.gross_value for o in result.orders)

    if total_gross > 0 and result.orders:
        commission_rate = (total_commission / total_gross) * 100
        for order in result.orders:
            order.commission_amount = (order.gross_value / total_gross) * total_commission
            order.commission_rate = commission_rate
            order.net_payout = order.gross_value - order.commission_amount

    if result.orders:
        dates = [o.order_datetime for o in result.orders if o.order_datetime]
        if dates:
            result.period_start = min(dates)
            result.period_end = max(dates)

    return result
