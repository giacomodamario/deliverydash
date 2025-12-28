import pandas as pd
from datetime import datetime
from typing import Optional
from .base import Platform, ParsedOrder, ParsedInvoice


def parse_glovo_datetime(dt_str) -> Optional[datetime]:
    if pd.isna(dt_str) or not dt_str:
        return None
    dt_str = str(dt_str).strip()
    formats = [
        "%Y-%d-%m %H:%M",
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    return None


def parse_glovo_invoice(filepath: str) -> ParsedInvoice:
    result = ParsedInvoice(
        platform=Platform.GLOVO,
        filename=filepath,
        parse_date=datetime.now()
    )

    try:
        df = pd.read_csv(filepath, encoding='utf-8')
    except Exception as e:
        result.errors.append(f"Failed to read file: {e}")
        return result

    col_mapping = {
        'Glovo Code': 'order_id',
        'Notification Partner Time': 'datetime',
        'Description': 'description',
        'Store Name': 'restaurant_name',
        'Store Address': 'restaurant_address',
        'Child Store Address Id': 'store_id',
        'Payment Method': 'payment_method',
        'Price of Products': 'gross_value',
        'Product Promotion Paid by Partner': 'promo_partner',
        'Flash Offer Promotion Paid by Partner': 'flash_promo',
        'Charged to Partner Base': 'charged_base',
        'Glovo platform fee': 'platform_fee',
        'Total Charged to Partner': 'total_charged',
        'Total Charged to Partner Percentage': 'commission_rate',
        'Delivery promotion paid by partner': 'delivery_promo',
        'Refunds (Incidents)': 'refunds',
        'Products paid in cash': 'cash_products',
        'Delivery Price paid in cash': 'cash_delivery',
        'Meal vouchers discounts': 'meal_vouchers',
        'Incidents to pay partner': 'incidents_credit',
        'Product with Incidents': 'incident_product',
        'Incidents Glovo Platform Fee': 'incidents_fee',
        'Wait Time Fee': 'wait_time_fee',
        'Wait Time Fee Refund': 'wait_time_refund',
        'Prime Order Vendor Fee': 'prime_fee',
        'Flash Deals Fee': 'flash_deals_fee'
    }

    df.columns = df.columns.str.strip()
    df = df.rename(columns={k: v for k, v in col_mapping.items() if k in df.columns})

    for _, row in df.iterrows():
        order_id = str(row.get('order_id', ''))
        if not order_id or pd.isna(order_id):
            continue

        gross = float(row.get('gross_value', 0) or 0)
        platform_fee = float(row.get('platform_fee', 0) or 0)
        commission_rate = float(row.get('commission_rate', 0) or 0)
        promo_partner = float(row.get('promo_partner', 0) or 0)
        flash_promo = float(row.get('flash_promo', 0) or 0)
        delivery_promo = float(row.get('delivery_promo', 0) or 0)
        refunds = float(row.get('refunds', 0) or 0)
        cash_products = float(row.get('cash_products', 0) or 0)
        cash_delivery = float(row.get('cash_delivery', 0) or 0)
        wait_fee = float(row.get('wait_time_fee', 0) or 0)
        wait_refund = float(row.get('wait_time_refund', 0) or 0)
        prime_fee = float(row.get('prime_fee', 0) or 0)
        flash_deals_fee = float(row.get('flash_deals_fee', 0) or 0)
        charged_base = float(row.get('charged_base', 0) or 0)
        store_id = str(row.get('store_id', ''))

        net_payout = charged_base - platform_fee

        order = ParsedOrder(
            platform=Platform.GLOVO,
            order_id=order_id,
            order_number=order_id,
            restaurant_name=str(row.get('restaurant_name', '')),
            restaurant_address=str(row.get('restaurant_address', '')),
            order_datetime=parse_glovo_datetime(row.get('datetime')),
            gross_value=gross,
            commission_amount=platform_fee,
            commission_rate=commission_rate,
            vat_amount=0.0,
            net_payout=net_payout,
            promo_restaurant_funded=promo_partner + flash_promo + delivery_promo,
            refund_amount=refunds,
            cash_payment_adjustment=cash_products + cash_delivery,
            is_cash_order=cash_products > 0,
            wait_time_fee=wait_fee - wait_refund,
            prime_fee=prime_fee,
            flash_deals_fee=flash_deals_fee,
            store_id=store_id,
            items_description=str(row.get('description', ''))
        )

        result.orders.append(order)
        if not result.restaurant_name:
            result.restaurant_name = order.restaurant_name

    if result.orders:
        dates = [o.order_datetime for o in result.orders if o.order_datetime]
        if dates:
            result.period_start = min(dates)
            result.period_end = max(dates)

    return result
