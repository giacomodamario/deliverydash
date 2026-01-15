#!/usr/bin/env python3
"""
Compare Deliveroo vs Glovo data for 9 Italian stores.
Period: Jan 8-14, 2026
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass

from parsers.deliveroo import parse_deliveroo_invoice
from parsers.base import Platform, ParsedOrder, ParsedInvoice

# Store mapping: City -> (Deliveroo name pattern, Glovo name pattern)
STORE_MAPPING = {
    'Milano': ('Brera', 'Via Broletto'),
    'Brescia': ('Brescia', 'Corso Giuseppe Zanardelli'),
    'Roma': ('Roma Colonna', 'Via Marcantonio Colonna'),
    'Firenze': ('Firenze', 'Piazza degli Ottaviani'),
    'Torino': ('Lingotto', 'Via Santa Croce'),
    'Napoli': ('Napoli Chiaia', 'Via Chiaia'),
    'Verona': ('Verona', 'Largo Guido Gonella'),
    'Catania': ('Catania', 'Piazza Giovanni Verga'),
    'Palermo': ('Palermo', 'Via Filippo Pecoraino'),
}

@dataclass
class StoreMetrics:
    """Normalized metrics for a single store."""
    city: str
    platform: str
    store_name: str
    order_count: int = 0
    gross_revenue: float = 0.0
    commission: float = 0.0
    commission_rate: float = 0.0
    platform_fees: float = 0.0
    ads_marketing: float = 0.0
    vendor_discounts: float = 0.0
    platform_discounts: float = 0.0
    refunds: float = 0.0
    net_payout: float = 0.0
    # Platform-specific fields
    discount_commission: float = 0.0  # Deliveroo only
    wait_time_fee: float = 0.0  # Glovo only
    online_payment_fee: float = 0.0  # Glovo only
    vendor_charges: float = 0.0  # Glovo only
    service_fee: float = 0.0  # Glovo only
    packaging_charges: float = 0.0  # Glovo only
    min_order_fee: float = 0.0  # Glovo only


def load_deliveroo_data(data_dir: Path) -> Dict[str, StoreMetrics]:
    """Load and parse Deliveroo CSV files, return metrics by city."""
    metrics = {}
    csv_files = list(data_dir.glob('deliveroo_statement_*.csv'))

    print(f"\nScanning {len(csv_files)} Deliveroo CSV files...")

    for csv_file in csv_files:
        try:
            invoice = parse_deliveroo_invoice(str(csv_file), verbose=False)
            if not invoice.orders:
                continue

            restaurant_name = invoice.restaurant_name

            # Match to city
            matched_city = None
            for city, (deliv_pattern, _) in STORE_MAPPING.items():
                if deliv_pattern.lower() in restaurant_name.lower():
                    matched_city = city
                    break

            if not matched_city:
                continue

            # Skip if already have data for this city (take first/most recent)
            if matched_city in metrics:
                continue

            # Aggregate orders
            m = StoreMetrics(
                city=matched_city,
                platform='Deliveroo',
                store_name=restaurant_name,
            )

            for order in invoice.orders:
                m.order_count += 1
                m.gross_revenue += order.gross_value
                m.commission += order.commission_amount
                m.platform_fees += order.vat_amount
                m.ads_marketing += order.ad_fee
                m.vendor_discounts += order.promo_restaurant_funded
                m.platform_discounts += order.promo_platform_funded
                m.refunds += order.refund_amount
                m.net_payout += order.net_payout
                m.discount_commission += order.discount_commission

            if m.gross_revenue > 0:
                m.commission_rate = (m.commission / m.gross_revenue) * 100

            metrics[matched_city] = m
            print(f"  ✓ {matched_city}: {restaurant_name} ({m.order_count} orders, €{m.gross_revenue:.2f})")

        except Exception as e:
            print(f"  Warning: Could not parse {csv_file.name}: {e}")
            continue

    return metrics


def load_glovo_data(csv_path: Path) -> Dict[str, StoreMetrics]:
    """Load and parse Glovo CSV, return metrics by city."""
    metrics = {}

    print(f"\nLoading Glovo data from {csv_path.name}...")
    df = pd.read_csv(csv_path)
    print(f"  Total rows: {len(df)}")

    # Filter to only delivered orders
    df = df[df['Order status'] == 'Delivered']
    print(f"  Delivered orders: {len(df)}")

    for city, (_, glovo_pattern) in STORE_MAPPING.items():
        # Filter to this store
        store_df = df[df['Restaurant name'].str.contains(glovo_pattern, case=False, na=False)]

        if store_df.empty:
            print(f"  ✗ {city}: No orders found for pattern '{glovo_pattern}'")
            continue

        store_name = store_df['Restaurant name'].iloc[0]

        # Calculate metrics
        m = StoreMetrics(
            city=city,
            platform='Glovo',
            store_name=store_name,
            order_count=len(store_df),
            gross_revenue=store_df['Subtotal'].sum(),
            commission=store_df['Commission'].sum(),
            service_fee=store_df['Service fee'].sum(),
            packaging_charges=store_df['Packaging charges'].sum(),
            min_order_fee=store_df['Minimum order value fee'].sum(),
            online_payment_fee=store_df['Online Payment Fee'].sum(),
            vendor_charges=store_df['Vendor Charges'].sum(),
            ads_marketing=store_df['Ads Fee'].sum() + store_df['Marketing Fees'].sum(),
            vendor_discounts=store_df['Discount Funded by Vendor'].sum() + store_df['Voucher Funded by Vendor'].sum(),
            platform_discounts=store_df['Platform-Funded Discount'].sum() + store_df['Platform-Funded Voucher'].sum(),
            refunds=store_df['Vendor Refunds'].sum(),
            wait_time_fee=store_df['Wait time fee'].sum(),
        )

        # Platform fees = service + packaging + min order
        m.platform_fees = m.service_fee + m.packaging_charges + m.min_order_fee

        # Calculate net payout
        m.net_payout = store_df['Payout Amount'].sum()

        # Commission rate
        if m.gross_revenue > 0:
            m.commission_rate = (m.commission / m.gross_revenue) * 100

        metrics[city] = m
        print(f"  ✓ {city}: {store_name} ({m.order_count} orders, €{m.gross_revenue:.2f})")

    return metrics


def print_comparison_table(deliveroo: Dict[str, StoreMetrics], glovo: Dict[str, StoreMetrics]):
    """Print a side-by-side comparison table."""
    print("\n" + "="*100)
    print("PLATFORM COMPARISON BY STORE")
    print("="*100)

    # Header
    print(f"{'City':<12} | {'Platform':<10} | {'Orders':>7} | {'Gross €':>10} | {'Comm %':>7} | {'Ads €':>8} | {'Disc €':>8} | {'Net €':>10}")
    print("-"*100)

    all_cities = sorted(set(deliveroo.keys()) | set(glovo.keys()))

    totals = {'deliveroo': StoreMetrics(city='TOTAL', platform='Deliveroo', store_name=''),
              'glovo': StoreMetrics(city='TOTAL', platform='Glovo', store_name='')}

    for city in all_cities:
        # Deliveroo row
        if city in deliveroo:
            d = deliveroo[city]
            print(f"{city:<12} | {'Deliveroo':<10} | {d.order_count:>7} | {d.gross_revenue:>10.2f} | {d.commission_rate:>6.1f}% | {d.ads_marketing:>8.2f} | {d.vendor_discounts:>8.2f} | {d.net_payout:>10.2f}")
            totals['deliveroo'].order_count += d.order_count
            totals['deliveroo'].gross_revenue += d.gross_revenue
            totals['deliveroo'].commission += d.commission
            totals['deliveroo'].ads_marketing += d.ads_marketing
            totals['deliveroo'].vendor_discounts += d.vendor_discounts
            totals['deliveroo'].net_payout += d.net_payout
        else:
            print(f"{city:<12} | {'Deliveroo':<10} | {'N/A':>7} | {'N/A':>10} | {'N/A':>7} | {'N/A':>8} | {'N/A':>8} | {'N/A':>10}")

        # Glovo row
        if city in glovo:
            g = glovo[city]
            print(f"{'':<12} | {'Glovo':<10} | {g.order_count:>7} | {g.gross_revenue:>10.2f} | {g.commission_rate:>6.1f}% | {g.ads_marketing:>8.2f} | {g.vendor_discounts:>8.2f} | {g.net_payout:>10.2f}")
            totals['glovo'].order_count += g.order_count
            totals['glovo'].gross_revenue += g.gross_revenue
            totals['glovo'].commission += g.commission
            totals['glovo'].ads_marketing += g.ads_marketing
            totals['glovo'].vendor_discounts += g.vendor_discounts
            totals['glovo'].net_payout += g.net_payout
        else:
            print(f"{'':<12} | {'Glovo':<10} | {'N/A':>7} | {'N/A':>10} | {'N/A':>7} | {'N/A':>8} | {'N/A':>8} | {'N/A':>10}")

        print("-"*100)

    # Totals
    print(f"{'TOTAL':<12} | {'Deliveroo':<10} | {totals['deliveroo'].order_count:>7} | {totals['deliveroo'].gross_revenue:>10.2f} | {(totals['deliveroo'].commission/totals['deliveroo'].gross_revenue*100) if totals['deliveroo'].gross_revenue > 0 else 0:>6.1f}% | {totals['deliveroo'].ads_marketing:>8.2f} | {totals['deliveroo'].vendor_discounts:>8.2f} | {totals['deliveroo'].net_payout:>10.2f}")
    print(f"{'':<12} | {'Glovo':<10} | {totals['glovo'].order_count:>7} | {totals['glovo'].gross_revenue:>10.2f} | {(totals['glovo'].commission/totals['glovo'].gross_revenue*100) if totals['glovo'].gross_revenue > 0 else 0:>6.1f}% | {totals['glovo'].ads_marketing:>8.2f} | {totals['glovo'].vendor_discounts:>8.2f} | {totals['glovo'].net_payout:>10.2f}")
    print("="*100)

    return totals


def export_to_csv(deliveroo: Dict[str, StoreMetrics], glovo: Dict[str, StoreMetrics], output_path: Path):
    """Export comparison data to CSV."""
    rows = []
    for city in sorted(set(deliveroo.keys()) | set(glovo.keys())):
        for platform, data in [('Deliveroo', deliveroo), ('Glovo', glovo)]:
            if city in data:
                m = data[city]
                rows.append({
                    'City': city,
                    'Platform': platform,
                    'Store Name': m.store_name,
                    'Orders': m.order_count,
                    'Gross Revenue': m.gross_revenue,
                    'Commission': m.commission,
                    'Commission Rate %': m.commission_rate,
                    'Platform Fees': m.platform_fees,
                    'Ads & Marketing': m.ads_marketing,
                    'Vendor Discounts': m.vendor_discounts,
                    'Platform Discounts': m.platform_discounts,
                    'Refunds': m.refunds,
                    'Net Payout': m.net_payout,
                    'Avg Basket Size': m.gross_revenue / m.order_count if m.order_count > 0 else 0,
                    'Net Margin %': (m.net_payout / m.gross_revenue * 100) if m.gross_revenue > 0 else 0,
                    # Platform-specific
                    'Discount Commission (Deliveroo)': m.discount_commission,
                    'Service Fee (Glovo)': m.service_fee,
                    'Packaging (Glovo)': m.packaging_charges,
                    'Wait Time Fee (Glovo)': m.wait_time_fee,
                })

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"\nExported to {output_path}")


def main():
    base_dir = Path(__file__).parent.parent
    deliveroo_dir = base_dir / 'data' / 'downloads' / 'deliveroo'
    glovo_csv = base_dir / 'data' / 'downloads' / 'glovo' / 'glovo_orders_20260114_195722.csv'
    output_dir = base_dir / 'data' / 'analysis'
    output_dir.mkdir(parents=True, exist_ok=True)

    print("="*60)
    print("DELIVEROO vs GLOVO - 9 Italian Stores Comparison")
    print("Period: Jan 8-14, 2026")
    print("="*60)

    # Load data
    deliveroo_metrics = load_deliveroo_data(deliveroo_dir)
    glovo_metrics = load_glovo_data(glovo_csv)

    # Check coverage
    print(f"\n✓ Deliveroo: {len(deliveroo_metrics)}/9 stores")
    print(f"✓ Glovo: {len(glovo_metrics)}/9 stores")

    if not deliveroo_metrics:
        print("\n⚠ No Deliveroo Italian store data found!")
        print("  Please run the download script first.")
        return

    # Print comparison
    totals = print_comparison_table(deliveroo_metrics, glovo_metrics)

    # Export to CSV
    export_to_csv(deliveroo_metrics, glovo_metrics, output_dir / 'platform_comparison.csv')

    # Summary insights
    print("\n" + "="*60)
    print("KEY INSIGHTS")
    print("="*60)

    d_total = totals['deliveroo']
    g_total = totals['glovo']

    if d_total.order_count > 0 and g_total.order_count > 0:
        print(f"\n📊 Order Volume:")
        print(f"   Glovo: {g_total.order_count} orders")
        print(f"   Deliveroo: {d_total.order_count} orders")
        print(f"   Glovo has {g_total.order_count - d_total.order_count:+} more orders ({g_total.order_count/d_total.order_count:.1f}x)")

        print(f"\n💰 Revenue:")
        print(f"   Glovo: €{g_total.gross_revenue:,.2f}")
        print(f"   Deliveroo: €{d_total.gross_revenue:,.2f}")

        d_margin = (d_total.net_payout / d_total.gross_revenue * 100) if d_total.gross_revenue > 0 else 0
        g_margin = (g_total.net_payout / g_total.gross_revenue * 100) if g_total.gross_revenue > 0 else 0

        print(f"\n📈 Net Margin (Net/Gross):")
        print(f"   Deliveroo: {d_margin:.1f}%")
        print(f"   Glovo: {g_margin:.1f}%")
        print(f"   {'Deliveroo' if d_margin > g_margin else 'Glovo'} has better margins by {abs(d_margin - g_margin):.1f}pp")

        d_basket = d_total.gross_revenue / d_total.order_count
        g_basket = g_total.gross_revenue / g_total.order_count

        print(f"\n🛒 Average Basket Size:")
        print(f"   Deliveroo: €{d_basket:.2f}")
        print(f"   Glovo: €{g_basket:.2f}")


if __name__ == "__main__":
    main()
