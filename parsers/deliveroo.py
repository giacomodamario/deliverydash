import pandas as pd
import re
from datetime import datetime
from typing import Optional
from io import StringIO
from .base import Platform, ParsedOrder, ParsedInvoice, parse_european_number


def parse_deliveroo_datetime(dt_str) -> Optional[datetime]:
    """Parse datetime from various formats."""
    if pd.isna(dt_str) or not dt_str:
        return None
    dt_str = str(dt_str).strip()

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    return None


def parse_commission_rate(rate_str) -> float:
    """Parse commission rate like '30%' or '30,5%'."""
    if pd.isna(rate_str) or not rate_str:
        return 0.0
    rate_str = str(rate_str)
    match = re.search(r'([\d,\.]+)\s*%', rate_str)
    if match:
        return parse_european_number(match.group(1))
    return 0.0


def is_valid_order_id(order_id: str) -> bool:
    """Check if order_id looks like a real order ID (not '0' or a date)."""
    if not order_id or order_id == '0':
        return False
    # Check if it's a date (YYYY-MM-DD format)
    if re.match(r'^\d{4}-\d{2}-\d{2}', order_id):
        return False
    return True


def parse_deliveroo_invoice(filepath: str, verbose: bool = False) -> ParsedInvoice:
    """Parse a Deliveroo statement CSV file."""
    result = ParsedInvoice(
        platform=Platform.DELIVEROO,
        filename=filepath,
        parse_date=datetime.now()
    )

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(filepath, 'r', encoding='latin-1') as f:
                content = f.read()
        except Exception as e:
            result.errors.append(f"Failed to read file: {e}")
            return result
    except Exception as e:
        result.errors.append(f"Failed to read file: {e}")
        return result

    lines = content.split('\n')

    # Skip first line if it looks like a filename
    start_idx = 0
    if lines and (lines[0].endswith('.csv') or lines[0].endswith('.CSV') or 'statement' in lines[0].lower()):
        start_idx = 1

    # Find sections
    section_markers = [
        "Orders and related adjustments",
        "Payments for contested customer refunds",
        "Other payments and fees"
    ]

    sections = []
    current_section = {"name": "header", "lines": []}

    for i, line in enumerate(lines[start_idx:], start=start_idx):
        stripped = line.strip()

        # Check if this is a section header
        is_section_header = False
        for marker in section_markers:
            if marker.lower() in stripped.lower():
                is_section_header = True
                if current_section["lines"]:
                    sections.append(current_section)
                current_section = {"name": marker, "lines": []}
                break

        if not is_section_header and stripped:
            current_section["lines"].append(line)

    if current_section["lines"]:
        sections.append(current_section)

    if verbose:
        print(f"  Found {len(sections)} sections")

    orders_by_id = {}

    # Track standalone fees (not linked to orders)
    standalone_ad_fees = 0.0
    standalone_discount_commission = 0.0
    standalone_refunds = 0.0

    # Column name mapping (Italian -> English)
    col_mapping = {
        'nome del ristorante': 'restaurant_name',
        "numero d'ordine": 'order_number',
        'data e ora della consegna (utc)': 'datetime',
        'data e ora del ritiro (utc)': 'datetime',
        'attività': 'activity',
        "valore dell'ordine (€)": 'order_value',
        "valore dell'ordine": 'order_value',
        'valore netto della rettifica (€)': 'adjustment_value',
        'valore netto della rettifica': 'adjustment_value',
        'tasso di commissione deliveroo': 'commission_rate',
        'commissione deliveroo (€)': 'commission',
        'commissione deliveroo': 'commission',
        'commissione / rettifica - tasso del iva': 'vat_rate',
        'commissione / rettifica iva (€)': 'vat',
        'commissione / rettifica iva': 'vat',
        'totale da pagare': 'total_payout',
        'nota': 'notes',
        "id dell'ordine": 'order_id',
        'id ordine': 'order_id',
    }

    for section in sections:
        if not section["lines"]:
            continue

        section_text = '\n'.join(section["lines"])

        try:
            # Try to parse as CSV
            df = pd.read_csv(StringIO(section_text), encoding='utf-8', on_bad_lines='skip')
        except Exception as e:
            if verbose:
                print(f"  Warning: Could not parse section '{section['name']}': {e}")
            continue

        if df.empty:
            continue

        # Normalize column names
        df.columns = df.columns.str.strip().str.lower()

        # Apply mapping
        rename_map = {}
        for orig_col in df.columns:
            if orig_col in col_mapping:
                rename_map[orig_col] = col_mapping[orig_col]
        df = df.rename(columns=rename_map)

        if verbose:
            print(f"  Section '{section['name']}': {len(df)} rows")

        for idx, row in df.iterrows():
            try:
                # Get order ID
                order_id = row.get('order_id', '')
                if pd.isna(order_id):
                    order_id = ''
                order_id = str(order_id).strip()

                activity = str(row.get('activity', '')).strip()

                notes = str(row.get('notes', '') if not pd.isna(row.get('notes', '')) else '')
                adjustment_value = parse_european_number(row.get('adjustment_value'))

                # Main order (Consegna = Delivery, Ritiro = Pickup)
                if activity in ['Consegna', 'Ritiro', 'Delivery', 'Pickup']:
                    if not is_valid_order_id(order_id):
                        continue

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
                        notes=notes
                    )

                    # Check for cash order
                    if 'Pagamento in contanti' in notes or 'Cash' in notes:
                        order.is_cash_order = True

                    # Check for platform promo in order notes
                    # "Sconto offerta Marketer" = Platform-funded discount
                    if 'Sconto offerta Marketer' in notes or 'Marketer' in notes:
                        match = re.search(r'Sconto offerta Marketer[:\s]*([\d,\.]+)', notes)
                        if match:
                            # Use float() for notes-extracted values (not European format)
                            order.promo_platform_funded = float(match.group(1).replace(',', '.'))

                    # Check for restaurant discount in notes
                    # "Sconto del ristorante" or "Restaurant discount"
                    if 'Sconto del ristorante' in notes or 'Restaurant discount' in notes.lower():
                        match = re.search(r'Sconto del ristorante[:\s]*([\d,\.]+)', notes, re.IGNORECASE)
                        if match:
                            # Use float() for notes-extracted values (not European format)
                            order.promo_restaurant_funded = float(match.group(1).replace(',', '.'))

                    orders_by_id[order_id] = order
                    if order.restaurant_name:
                        result.restaurant_name = order.restaurant_name

                # Customer refund (Rimborso al cliente)
                elif 'Rimborso' in activity or 'Refund' in activity:
                    refund_amount = abs(adjustment_value)
                    if is_valid_order_id(order_id) and order_id in orders_by_id:
                        orders_by_id[order_id].refund_amount = refund_amount
                        # Parse refund reason and fault from notes
                        reason_match = re.search(r'[Rr]efund\s*reason[:\s]+([^,\n]+)', notes)
                        if reason_match:
                            orders_by_id[order_id].refund_reason = reason_match.group(1).strip()
                        fault_match = re.search(r'[Pp]arty\s*at\s*fault[:\s]+([^,\n]+)', notes)
                        if fault_match:
                            orders_by_id[order_id].refund_fault = fault_match.group(1).strip()
                    else:
                        # Standalone refund
                        standalone_refunds += refund_amount

                # Ads fee (Annunci Marketer) - usually in "Other payments and fees" section
                elif 'Annunci' in activity or ('Marketer' in activity and 'Sconto' not in activity):
                    ad_amount = abs(adjustment_value)
                    if is_valid_order_id(order_id) and order_id in orders_by_id:
                        orders_by_id[order_id].ad_fee += ad_amount
                    else:
                        # Standalone ad fee (order_id is "0" or a date)
                        standalone_ad_fees += ad_amount
                        if verbose:
                            print(f"    Standalone ad fee: {ad_amount}")

                # Discount commission (Correzione della fattura a debito)
                # This is commission charged on restaurant-funded discounts
                elif 'Correzione' in activity or 'fattura' in activity.lower():
                    if 'commission on funded discount' in notes.lower() or 'commissione' in notes.lower():
                        disc_comm = abs(adjustment_value)
                        if is_valid_order_id(order_id) and order_id in orders_by_id:
                            orders_by_id[order_id].discount_commission += disc_comm
                        else:
                            standalone_discount_commission += disc_comm

                # Cash payment adjustment
                elif 'contanti' in activity.lower() or 'cash' in activity.lower():
                    if is_valid_order_id(order_id) and order_id in orders_by_id:
                        orders_by_id[order_id].cash_payment_adjustment = abs(adjustment_value)
                        orders_by_id[order_id].is_cash_order = True

                # Restaurant-funded voucher/promo/discount
                # "Sconto" without "Marketer" is typically restaurant-funded
                elif 'sconto' in activity.lower() and 'marketer' not in activity.lower():
                    promo_amount = abs(adjustment_value)
                    if is_valid_order_id(order_id) and order_id in orders_by_id:
                        orders_by_id[order_id].promo_restaurant_funded += promo_amount

                # Generic voucher - usually platform
                elif 'voucher' in activity.lower():
                    promo_amount = abs(adjustment_value)
                    if is_valid_order_id(order_id) and order_id in orders_by_id:
                        orders_by_id[order_id].promo_platform_funded += promo_amount

            except Exception as e:
                if verbose:
                    print(f"  Error processing row {idx}: {e}")
                continue

    result.orders = list(orders_by_id.values())

    # Distribute standalone fees to orders proportionally if we have orders
    if result.orders and (standalone_ad_fees > 0 or standalone_discount_commission > 0 or standalone_refunds > 0):
        # Add to invoice-level tracking
        result.fees.append({
            'type': 'ad_fee',
            'amount': standalone_ad_fees,
            'description': 'Annunci Marketer (standalone)'
        })
        result.fees.append({
            'type': 'discount_commission',
            'amount': standalone_discount_commission,
            'description': 'Discount commission (standalone)'
        })

        if verbose:
            print(f"  Standalone fees: ad={standalone_ad_fees}, disc_comm={standalone_discount_commission}, refunds={standalone_refunds}")

        # Distribute proportionally by gross value
        total_gross = sum(o.gross_value for o in result.orders)
        if total_gross > 0:
            for order in result.orders:
                proportion = order.gross_value / total_gross
                order.ad_fee += standalone_ad_fees * proportion
                order.discount_commission += standalone_discount_commission * proportion
                # Don't distribute refunds - they should stay with their original orders

    if result.orders:
        dates = [o.order_datetime for o in result.orders if o.order_datetime]
        if dates:
            result.period_start = min(dates)
            result.period_end = max(dates)

    if verbose:
        print(f"  Parsed {len(result.orders)} orders")
        if result.orders:
            total_ad = sum(o.ad_fee for o in result.orders)
            total_disc = sum(o.discount_commission for o in result.orders)
            total_rest_promo = sum(o.promo_restaurant_funded for o in result.orders)
            total_plat_promo = sum(o.promo_platform_funded for o in result.orders)
            print(f"  Totals: ad_fee={total_ad}, discount_comm={total_disc}, rest_promo={total_rest_promo}, plat_promo={total_plat_promo}")

    return result
