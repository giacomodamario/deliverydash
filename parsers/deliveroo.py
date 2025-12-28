import pandas as pd
import re
from datetime import datetime
from typing import Optional
from io import StringIO
from .base import Platform, ParsedOrder, ParsedInvoice, parse_european_number


def parse_deliveroo_datetime(dt_str) -> Optional[datetime]:
    if pd.isna(dt_str) or not dt_str:
        return None
    try:
        return datetime.strptime(str(dt_str).strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            return datetime.strptime(str(dt_str).strip(), "%Y-%m-%d")
        except ValueError:
            return None


def parse_commission_rate(rate_str) -> float:
    if pd.isna(rate_str) or not rate_str:
        return 0.0
    rate_str = str(rate_str)
    match = re.search(r'([\d,\.]+)%', rate_str)
    if match:
        return parse_european_number(match.group(1))
    return 0.0


def parse_deliveroo_invoice(filepath: str) -> ParsedInvoice:
    result = ParsedInvoice(
        platform=Platform.DELIVEROO,
        filename=filepath,
        parse_date=datetime.now()
    )

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        result.errors.append(f"Failed to read file: {e}")
        return result

    lines = content.split('\n')
    sections = []
    current_section = {"name": "", "start": 0, "lines": []}

    section_headers = [
        "Orders and related adjustments",
        "Payments for contested customer refunds",
        "Other payments and fees"
    ]

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped in section_headers:
            if current_section["lines"]:
                sections.append(current_section)
            current_section = {"name": stripped, "start": i, "lines": []}
        else:
            current_section["lines"].append(line)

    if current_section["lines"]:
        sections.append(current_section)

    orders_by_id = {}

    for section in sections:
        if not section["lines"]:
            continue

        section_text = '\n'.join(section["lines"])

        try:
            df = pd.read_csv(StringIO(section_text), encoding='utf-8')
        except Exception as e:
            result.errors.append(f"Failed to parse section {section['name']}: {e}")
            continue

        if df.empty:
            continue

        col_mapping = {
            'Nome del ristorante': 'restaurant_name',
            "Numero d'ordine": 'order_number',
            'Data e ora della consegna (UTC)': 'datetime',
            'Attività': 'activity',
            "Valore dell'ordine (€)": 'order_value',
            'Valore netto della rettifica (€)': 'adjustment_value',
            'Tasso di commissione Deliveroo': 'commission_rate',
            'Commissione Deliveroo (€)': 'commission',
            'Commissione / rettifica - tasso del IVA': 'vat_rate',
            'Commissione / rettifica IVA (€)': 'vat',
            'Totale da pagare': 'total_payout',
            'Nota': 'notes',
            "ID dell'ordine": 'order_id'
        }

        df.columns = df.columns.str.strip()
        df = df.rename(columns={k: v for k, v in col_mapping.items() if k in df.columns})

        for _, row in df.iterrows():
            order_id = str(row.get('order_id', ''))
            if not order_id or pd.isna(order_id):
                continue

            activity = str(row.get('activity', ''))

            if activity == 'Consegna':
                order = ParsedOrder(
                    platform=Platform.DELIVEROO,
                    order_id=order_id,
                    order_number=str(row.get('order_number', '')),
                    restaurant_name=str(row.get('restaurant_name', '')),
                    restaurant_address='',
                    order_datetime=parse_deliveroo_datetime(row.get('datetime')),
                    gross_value=parse_european_number(row.get('order_value')),
                    commission_amount=abs(parse_european_number(row.get('commission'))),
                    commission_rate=parse_commission_rate(row.get('commission_rate')),
                    vat_amount=abs(parse_european_number(row.get('vat'))),
                    net_payout=parse_european_number(row.get('total_payout')),
                    notes=str(row.get('notes', ''))
                )

                notes = str(row.get('notes', ''))
                if 'Pagamento in contanti' in notes or 'Cash' in notes:
                    order.is_cash_order = True

                if 'Sconto offerta Marketer' in notes:
                    match = re.search(r'Sconto offerta Marketer:\s*([\d,\.]+)', notes)
                    if match:
                        order.promo_platform_funded = parse_european_number(match.group(1))

                orders_by_id[order_id] = order
                result.restaurant_name = order.restaurant_name

            elif activity == 'Rimborso al cliente':
                if order_id in orders_by_id:
                    orders_by_id[order_id].refund_amount = abs(parse_european_number(row.get('adjustment_value')))
                    notes = str(row.get('notes', ''))
                    reason_match = re.search(r'Refund reason:\s*(\w+)', notes)
                    fault_match = re.search(r'Party at fault:\s*(\w+)', notes)
                    if reason_match:
                        orders_by_id[order_id].refund_reason = reason_match.group(1)
                    if fault_match:
                        orders_by_id[order_id].refund_fault = fault_match.group(1)

            elif 'Promozione con voucher' in activity:
                if order_id in orders_by_id:
                    orders_by_id[order_id].promo_restaurant_funded = abs(parse_european_number(row.get('adjustment_value')))

            elif activity == 'Pagamento in contanti':
                if order_id in orders_by_id:
                    orders_by_id[order_id].cash_payment_adjustment = abs(parse_european_number(row.get('adjustment_value')))
                    orders_by_id[order_id].is_cash_order = True

            elif activity == 'Annunci Marketer':
                result.fees.append({
                    'type': 'ad_fee',
                    'amount': abs(parse_european_number(row.get('adjustment_value'))),
                    'vat': abs(parse_european_number(row.get('vat'))),
                    'total': abs(parse_european_number(row.get('total_payout'))),
                    'date': parse_deliveroo_datetime(row.get('datetime')),
                    'notes': str(row.get('notes', ''))
                })

            elif 'Correzione della fattura' in activity:
                result.credits.append({
                    'type': 'commission_refund',
                    'amount': parse_european_number(row.get('adjustment_value')),
                    'vat': parse_european_number(row.get('vat')),
                    'total': parse_european_number(row.get('total_payout')),
                    'date': parse_deliveroo_datetime(row.get('datetime')),
                    'notes': str(row.get('notes', ''))
                })

    result.orders = list(orders_by_id.values())

    if result.orders:
        dates = [o.order_datetime for o in result.orders if o.order_datetime]
        if dates:
            result.period_start = min(dates)
            result.period_end = max(dates)

    return result
