#!/usr/bin/env python3
"""
Analyze Glovo data for 9 Italian stores.
Period: Jan 8-14, 2026

Note: Deliveroo data unavailable due to Cloudflare blocking.
This analysis focuses on Glovo metrics only.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from datetime import datetime
from typing import Dict
from dataclasses import dataclass

# Store mapping: City -> Glovo name pattern
STORE_MAPPING = {
    'Milano (Brera)': 'Via Broletto',
    'Brescia': 'Corso Giuseppe Zanardelli',
    'Roma': 'Via Marcantonio Colonna',
    'Firenze': 'Piazza degli Ottaviani',
    'Torino': 'Via Santa Croce',
    'Napoli': 'Via Chiaia',
    'Verona': 'Largo Guido Gonella',
    'Catania': 'Piazza Giovanni Verga',
    'Palermo': 'Via Filippo Pecoraino',
}

@dataclass
class StoreMetrics:
    """Metrics for a single store."""
    city: str
    store_name: str
    order_count: int = 0
    gross_revenue: float = 0.0
    commission: float = 0.0
    commission_rate: float = 0.0
    service_fee: float = 0.0
    packaging_charges: float = 0.0
    min_order_fee: float = 0.0
    online_payment_fee: float = 0.0
    vendor_charges: float = 0.0
    ads_fee: float = 0.0
    marketing_fees: float = 0.0
    wait_time_fee: float = 0.0
    vendor_discounts: float = 0.0
    vendor_vouchers: float = 0.0
    platform_discounts: float = 0.0
    platform_vouchers: float = 0.0
    refunds: float = 0.0
    net_payout: float = 0.0
    avg_basket_size: float = 0.0
    net_margin_pct: float = 0.0


def load_glovo_data(csv_path: Path) -> Dict[str, StoreMetrics]:
    """Load and parse Glovo CSV, return metrics by city."""
    metrics = {}

    print(f"\nLoading Glovo data from {csv_path.name}...")
    df = pd.read_csv(csv_path)
    print(f"  Total rows: {len(df)}")

    # Filter to only delivered orders
    df = df[df['Order status'] == 'Delivered']
    print(f"  Delivered orders: {len(df)}")

    for city, glovo_pattern in STORE_MAPPING.items():
        # Filter to this store
        store_df = df[df['Restaurant name'].str.contains(glovo_pattern, case=False, na=False)]

        if store_df.empty:
            print(f"  ✗ {city}: No orders found for pattern '{glovo_pattern}'")
            continue

        store_name = store_df['Restaurant name'].iloc[0]

        # Calculate metrics
        m = StoreMetrics(
            city=city,
            store_name=store_name,
            order_count=len(store_df),
            gross_revenue=store_df['Subtotal'].sum(),
            commission=store_df['Commission'].sum(),
            service_fee=store_df['Service fee'].sum(),
            packaging_charges=store_df['Packaging charges'].sum(),
            min_order_fee=store_df['Minimum order value fee'].sum(),
            online_payment_fee=store_df['Online Payment Fee'].sum(),
            vendor_charges=store_df['Vendor Charges'].sum(),
            ads_fee=store_df['Ads Fee'].sum(),
            marketing_fees=store_df['Marketing Fees'].sum(),
            wait_time_fee=store_df['Wait time fee'].sum(),
            vendor_discounts=store_df['Discount Funded by Vendor'].sum(),
            vendor_vouchers=store_df['Voucher Funded by Vendor'].sum(),
            platform_discounts=store_df['Platform-Funded Discount'].sum(),
            platform_vouchers=store_df['Platform-Funded Voucher'].sum(),
            refunds=store_df['Vendor Refunds'].sum(),
            net_payout=store_df['Payout Amount'].sum(),
        )

        # Calculated fields
        if m.gross_revenue > 0:
            m.commission_rate = (m.commission / m.gross_revenue) * 100
            m.net_margin_pct = (m.net_payout / m.gross_revenue) * 100
        if m.order_count > 0:
            m.avg_basket_size = m.gross_revenue / m.order_count

        metrics[city] = m
        print(f"  ✓ {city}: {store_name} ({m.order_count} orders, €{m.gross_revenue:.2f})")

    return metrics


def print_summary_table(metrics: Dict[str, StoreMetrics]):
    """Print a summary table."""
    print("\n" + "="*120)
    print("GLOVO - 9 ITALIAN STORES ANALYSIS (Jan 8-14, 2026)")
    print("="*120)

    # Header
    print(f"{'City':<18} | {'Orders':>7} | {'Gross €':>10} | {'Avg €':>8} | {'Comm %':>7} | {'Ads €':>8} | {'Disc €':>8} | {'Net €':>10} | {'Margin':>7}")
    print("-"*120)

    totals = StoreMetrics(city='TOTAL', store_name='All Stores')

    cities = sorted(metrics.keys())
    for city in cities:
        m = metrics[city]
        disc = m.vendor_discounts + m.vendor_vouchers + m.platform_discounts + m.platform_vouchers
        print(f"{city:<18} | {m.order_count:>7} | {m.gross_revenue:>10.2f} | {m.avg_basket_size:>8.2f} | {m.commission_rate:>6.1f}% | {m.ads_fee + m.marketing_fees:>8.2f} | {disc:>8.2f} | {m.net_payout:>10.2f} | {m.net_margin_pct:>6.1f}%")

        # Accumulate totals
        totals.order_count += m.order_count
        totals.gross_revenue += m.gross_revenue
        totals.commission += m.commission
        totals.ads_fee += m.ads_fee
        totals.marketing_fees += m.marketing_fees
        totals.vendor_discounts += m.vendor_discounts
        totals.vendor_vouchers += m.vendor_vouchers
        totals.platform_discounts += m.platform_discounts
        totals.platform_vouchers += m.platform_vouchers
        totals.net_payout += m.net_payout

    print("-"*120)

    # Calculate total derived metrics
    if totals.gross_revenue > 0:
        totals.commission_rate = (totals.commission / totals.gross_revenue) * 100
        totals.net_margin_pct = (totals.net_payout / totals.gross_revenue) * 100
    if totals.order_count > 0:
        totals.avg_basket_size = totals.gross_revenue / totals.order_count

    disc = totals.vendor_discounts + totals.vendor_vouchers + totals.platform_discounts + totals.platform_vouchers
    print(f"{'TOTAL':<18} | {totals.order_count:>7} | {totals.gross_revenue:>10.2f} | {totals.avg_basket_size:>8.2f} | {totals.commission_rate:>6.1f}% | {totals.ads_fee + totals.marketing_fees:>8.2f} | {disc:>8.2f} | {totals.net_payout:>10.2f} | {totals.net_margin_pct:>6.1f}%")
    print("="*120)

    return totals


def print_detailed_breakdown(metrics: Dict[str, StoreMetrics]):
    """Print detailed breakdown of fees and deductions."""
    print("\n" + "="*120)
    print("DETAILED FEE BREAKDOWN")
    print("="*120)

    print(f"{'City':<18} | {'Service':>8} | {'Packing':>8} | {'MinOrd':>8} | {'PayFee':>8} | {'VendChrg':>8} | {'WaitFee':>8} | {'Refunds':>8}")
    print("-"*120)

    for city in sorted(metrics.keys()):
        m = metrics[city]
        print(f"{city:<18} | {m.service_fee:>8.2f} | {m.packaging_charges:>8.2f} | {m.min_order_fee:>8.2f} | {m.online_payment_fee:>8.2f} | {m.vendor_charges:>8.2f} | {m.wait_time_fee:>8.2f} | {m.refunds:>8.2f}")

    print("="*120)


def print_discount_breakdown(metrics: Dict[str, StoreMetrics]):
    """Print breakdown of discount types."""
    print("\n" + "="*120)
    print("DISCOUNT BREAKDOWN (Vendor vs Platform Funded)")
    print("="*120)

    print(f"{'City':<18} | {'Vend Disc':>10} | {'Vend Vouch':>10} | {'Plat Disc':>10} | {'Plat Vouch':>10} | {'Total':>10} | {'% of Gross':>10}")
    print("-"*120)

    for city in sorted(metrics.keys()):
        m = metrics[city]
        total_disc = m.vendor_discounts + m.vendor_vouchers + m.platform_discounts + m.platform_vouchers
        pct = (total_disc / m.gross_revenue * 100) if m.gross_revenue > 0 else 0
        print(f"{city:<18} | {m.vendor_discounts:>10.2f} | {m.vendor_vouchers:>10.2f} | {m.platform_discounts:>10.2f} | {m.platform_vouchers:>10.2f} | {total_disc:>10.2f} | {pct:>9.1f}%")

    print("="*120)


def export_to_csv(metrics: Dict[str, StoreMetrics], output_path: Path):
    """Export to CSV."""
    rows = []
    for city in sorted(metrics.keys()):
        m = metrics[city]
        rows.append({
            'City': city,
            'Store Name': m.store_name,
            'Orders': m.order_count,
            'Gross Revenue': m.gross_revenue,
            'Avg Basket Size': m.avg_basket_size,
            'Commission': m.commission,
            'Commission Rate %': m.commission_rate,
            'Ads Fee': m.ads_fee,
            'Marketing Fees': m.marketing_fees,
            'Service Fee': m.service_fee,
            'Packaging Charges': m.packaging_charges,
            'Min Order Fee': m.min_order_fee,
            'Online Payment Fee': m.online_payment_fee,
            'Vendor Charges': m.vendor_charges,
            'Wait Time Fee': m.wait_time_fee,
            'Vendor Discounts': m.vendor_discounts,
            'Vendor Vouchers': m.vendor_vouchers,
            'Platform Discounts': m.platform_discounts,
            'Platform Vouchers': m.platform_vouchers,
            'Total Discounts': m.vendor_discounts + m.vendor_vouchers + m.platform_discounts + m.platform_vouchers,
            'Refunds': m.refunds,
            'Net Payout': m.net_payout,
            'Net Margin %': m.net_margin_pct,
        })

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"\nExported to {output_path}")


def main():
    base_dir = Path(__file__).parent.parent
    glovo_csv = base_dir / 'data' / 'downloads' / 'glovo' / 'glovo_orders_20260114_195722.csv'
    output_dir = base_dir / 'data' / 'analysis'
    output_dir.mkdir(parents=True, exist_ok=True)

    print("="*60)
    print("GLOVO ANALYSIS - 9 Italian Stores")
    print("Period: Jan 8-14, 2026")
    print("="*60)
    print("\nNote: Deliveroo data unavailable (Cloudflare blocking)")

    # Load data
    metrics = load_glovo_data(glovo_csv)

    # Check coverage
    print(f"\n✓ Found data for {len(metrics)}/9 target stores")

    if not metrics:
        print("\n⚠ No data found for target stores!")
        return

    # Print summaries
    totals = print_summary_table(metrics)
    print_detailed_breakdown(metrics)
    print_discount_breakdown(metrics)

    # Export to CSV
    export_to_csv(metrics, output_dir / 'glovo_analysis.csv')

    # Key insights
    print("\n" + "="*60)
    print("KEY INSIGHTS")
    print("="*60)

    # Top performers
    by_orders = sorted(metrics.values(), key=lambda x: x.order_count, reverse=True)
    by_revenue = sorted(metrics.values(), key=lambda x: x.gross_revenue, reverse=True)
    by_basket = sorted(metrics.values(), key=lambda x: x.avg_basket_size, reverse=True)
    by_margin = sorted(metrics.values(), key=lambda x: x.net_margin_pct, reverse=True)

    print(f"\n📊 Top by Order Volume:")
    for m in by_orders[:3]:
        print(f"   {m.city}: {m.order_count} orders")

    print(f"\n💰 Top by Revenue:")
    for m in by_revenue[:3]:
        print(f"   {m.city}: €{m.gross_revenue:,.2f}")

    print(f"\n🛒 Highest Average Basket:")
    for m in by_basket[:3]:
        print(f"   {m.city}: €{m.avg_basket_size:.2f}")

    print(f"\n📈 Best Net Margin:")
    for m in by_margin[:3]:
        print(f"   {m.city}: {m.net_margin_pct:.1f}%")

    # Ads/Marketing analysis
    total_ads = sum(m.ads_fee + m.marketing_fees for m in metrics.values())
    print(f"\n📢 Marketing Spend:")
    print(f"   Total Ads + Marketing: €{total_ads:,.2f}")
    print(f"   As % of Revenue: {(total_ads/totals.gross_revenue*100):.2f}%")

    # Discount analysis
    vendor_funded = sum(m.vendor_discounts + m.vendor_vouchers for m in metrics.values())
    platform_funded = sum(m.platform_discounts + m.platform_vouchers for m in metrics.values())
    print(f"\n🎁 Discount Split:")
    print(f"   Vendor-funded: €{vendor_funded:,.2f} ({vendor_funded/(vendor_funded+platform_funded)*100:.1f}%)")
    print(f"   Platform-funded: €{platform_funded:,.2f} ({platform_funded/(vendor_funded+platform_funded)*100:.1f}%)")


if __name__ == "__main__":
    main()
