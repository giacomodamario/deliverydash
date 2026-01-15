#!/usr/bin/env python3
"""
Generate visualizations for Deliveroo vs Glovo comparison.
9 Italian Stores - Jan 8-14, 2026
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import numpy as np


def create_visualizations(csv_path: Path, output_dir: Path):
    """Create all comparison visualizations."""

    df_raw = pd.read_csv(csv_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Set style
    plt.style.use('seaborn-v0_8-whitegrid')
    deliveroo_color = '#00CCBC'  # Deliveroo teal
    glovo_color = '#FFC244'      # Glovo yellow

    # Pivot the data to wide format
    cities = df_raw['City'].unique().tolist()

    # Create wide dataframe
    rows = []
    for city in cities:
        city_data = df_raw[df_raw['City'] == city]
        d_row = city_data[city_data['Platform'] == 'Deliveroo']
        g_row = city_data[city_data['Platform'] == 'Glovo']

        row = {'City': city}
        if len(d_row) > 0:
            d = d_row.iloc[0]
            row['D_Orders'] = d['Orders']
            row['D_Gross'] = d['Gross Revenue']
            row['D_Commission'] = d['Commission']
            row['D_VATComm'] = d['Platform Fees']  # VAT on commission for Deliveroo
            row['D_AdsFee'] = d['Ads & Marketing']
            row['D_VendorDisc'] = d['Vendor Discounts']
            row['D_Refunds'] = d['Refunds']
            row['D_NetPayout'] = d['Net Payout']
            row['D_AvgBasket'] = d['Avg Basket Size']
            row['D_NetMargin'] = d['Net Margin %']
        else:
            row['D_Orders'] = 0
            row['D_Gross'] = 0
            row['D_Commission'] = 0
            row['D_VATComm'] = 0
            row['D_AdsFee'] = 0
            row['D_VendorDisc'] = 0
            row['D_Refunds'] = 0
            row['D_NetPayout'] = 0
            row['D_AvgBasket'] = 0
            row['D_NetMargin'] = 0

        if len(g_row) > 0:
            g = g_row.iloc[0]
            row['G_Orders'] = g['Orders']
            row['G_Gross'] = g['Gross Revenue']
            row['G_ServiceFee'] = g.get('Service Fee (Glovo)', 0)
            row['G_Packaging'] = g.get('Packaging (Glovo)', 0)
            row['G_VendorDisc'] = g['Vendor Discounts']
            row['G_PlatformDisc'] = g['Platform Discounts']
            row['G_Refunds'] = g['Refunds']
            row['G_NetPayout'] = g['Net Payout']
            row['G_AvgBasket'] = g['Avg Basket Size']
            row['G_NetMargin'] = g['Net Margin %']
        else:
            row['G_Orders'] = 0
            row['G_Gross'] = 0
            row['G_ServiceFee'] = 0
            row['G_Packaging'] = 0
            row['G_VendorDisc'] = 0
            row['G_PlatformDisc'] = 0
            row['G_Refunds'] = 0
            row['G_NetPayout'] = 0
            row['G_AvgBasket'] = 0
            row['G_NetMargin'] = 0

        rows.append(row)

    df = pd.DataFrame(rows)

    n_cities = len(cities)
    x = np.arange(n_cities)
    width = 0.35

    # 1. Orders Comparison (Grouped Bar)
    fig, ax = plt.subplots(figsize=(14, 7))
    bars1 = ax.bar(x - width/2, df['D_Orders'], width, label='Deliveroo', color=deliveroo_color)
    bars2 = ax.bar(x + width/2, df['G_Orders'], width, label='Glovo', color=glovo_color)

    ax.set_ylabel('Number of Orders')
    ax.set_title('Order Volume: Deliveroo vs Glovo by Store (Jan 8-14, 2026)', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(cities, rotation=45, ha='right')
    ax.legend()

    ax.bar_label(bars1, padding=3, fontsize=8)
    ax.bar_label(bars2, padding=3, fontsize=8)

    plt.tight_layout()
    plt.savefig(output_dir / 'orders_comparison.png', dpi=150)
    plt.close()
    print(f"  ✓ orders_comparison.png")

    # 2. Revenue Comparison (Grouped Bar)
    fig, ax = plt.subplots(figsize=(14, 7))
    bars1 = ax.bar(x - width/2, df['D_Gross'], width, label='Deliveroo', color=deliveroo_color)
    bars2 = ax.bar(x + width/2, df['G_Gross'], width, label='Glovo', color=glovo_color)

    ax.set_ylabel('Gross Revenue (€)')
    ax.set_title('Revenue: Deliveroo vs Glovo by Store', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(cities, rotation=45, ha='right')
    ax.legend()

    ax.bar_label(bars1, fmt='%.0f', padding=3, fontsize=7)
    ax.bar_label(bars2, fmt='%.0f', padding=3, fontsize=7)

    plt.tight_layout()
    plt.savefig(output_dir / 'revenue_comparison.png', dpi=150)
    plt.close()
    print(f"  ✓ revenue_comparison.png")

    # 3. Net Margin Comparison
    fig, ax = plt.subplots(figsize=(14, 7))
    bars1 = ax.bar(x - width/2, df['D_NetMargin'], width, label='Deliveroo', color=deliveroo_color)
    bars2 = ax.bar(x + width/2, df['G_NetMargin'], width, label='Glovo', color=glovo_color)

    ax.set_ylabel('Net Margin (%)')
    ax.set_title('Net Margin: Deliveroo vs Glovo by Store', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(cities, rotation=45, ha='right')
    ax.legend()

    ax.bar_label(bars1, fmt='%.1f%%', padding=3, fontsize=8)
    ax.bar_label(bars2, fmt='%.1f%%', padding=3, fontsize=8)

    # Add averages
    d_avg = df['D_NetMargin'].mean()
    g_avg = df['G_NetMargin'].mean()
    ax.axhline(d_avg, color=deliveroo_color, linestyle='--', alpha=0.7, label=f'Deliveroo Avg: {d_avg:.1f}%')
    ax.axhline(g_avg, color=glovo_color, linestyle='--', alpha=0.7, label=f'Glovo Avg: {g_avg:.1f}%')

    plt.tight_layout()
    plt.savefig(output_dir / 'margin_comparison.png', dpi=150)
    plt.close()
    print(f"  ✓ margin_comparison.png")

    # 4. Average Basket Size Comparison
    fig, ax = plt.subplots(figsize=(14, 7))
    bars1 = ax.bar(x - width/2, df['D_AvgBasket'], width, label='Deliveroo', color=deliveroo_color)
    bars2 = ax.bar(x + width/2, df['G_AvgBasket'], width, label='Glovo', color=glovo_color)

    ax.set_ylabel('Average Basket Size (€)')
    ax.set_title('Average Basket Size: Deliveroo vs Glovo by Store', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(cities, rotation=45, ha='right')
    ax.legend()

    ax.bar_label(bars1, fmt='€%.2f', padding=3, fontsize=7)
    ax.bar_label(bars2, fmt='€%.2f', padding=3, fontsize=7)

    plt.tight_layout()
    plt.savefig(output_dir / 'basket_comparison.png', dpi=150)
    plt.close()
    print(f"  ✓ basket_comparison.png")

    # 5. Market Share Pie Charts
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # By Orders
    total_d_orders = df['D_Orders'].sum()
    total_g_orders = df['G_Orders'].sum()
    ax1.pie([total_d_orders, total_g_orders],
            labels=['Deliveroo', 'Glovo'],
            autopct='%1.1f%%',
            colors=[deliveroo_color, glovo_color],
            explode=(0.02, 0.02),
            startangle=90)
    ax1.set_title(f'Order Volume Share\n(Total: {total_d_orders + total_g_orders:,} orders)', fontweight='bold')

    # By Revenue
    total_d_rev = df['D_Gross'].sum()
    total_g_rev = df['G_Gross'].sum()
    ax2.pie([total_d_rev, total_g_rev],
            labels=['Deliveroo', 'Glovo'],
            autopct='%1.1f%%',
            colors=[deliveroo_color, glovo_color],
            explode=(0.02, 0.02),
            startangle=90)
    ax2.set_title(f'Revenue Share\n(Total: €{total_d_rev + total_g_rev:,.2f})', fontweight='bold')

    plt.suptitle('Platform Market Share (9 Italian Stores)', fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(output_dir / 'market_share.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ market_share.png")

    # 6. Revenue Waterfall Comparison
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 8))

    # Deliveroo waterfall
    d_gross = df['D_Gross'].sum()
    d_comm = df['D_Commission'].sum()
    d_vat = df['D_VATComm'].sum()
    d_ads = df['D_AdsFee'].sum()
    d_disc = df['D_VendorDisc'].sum()
    d_refunds = df['D_Refunds'].sum()
    d_net = df['D_NetPayout'].sum()

    categories = ['Gross', '-Commission', '-VAT', '-Ads', '-Discounts', '-Refunds', '=Net']
    d_values = [d_gross, -d_comm, -d_vat, -d_ads, -d_disc, -d_refunds, d_net]

    colors_d = ['green', 'red', 'red', 'red', 'red', 'red', 'blue']
    ax1.bar(categories, [abs(v) for v in d_values], color=colors_d)
    ax1.set_ylabel('Amount (€)')
    ax1.set_title(f'Deliveroo Revenue Breakdown\n(Net Margin: {d_net/d_gross*100:.1f}%)', fontweight='bold')
    ax1.set_xticklabels(categories, rotation=45, ha='right')

    for i, v in enumerate(d_values):
        ax1.text(i, abs(v) + 100, f'€{abs(v):,.0f}', ha='center', fontsize=8)

    # Glovo waterfall
    g_gross = df['G_Gross'].sum()
    g_service = df['G_ServiceFee'].sum()
    g_pkg = df['G_Packaging'].sum()
    g_disc = df['G_VendorDisc'].sum() + df['G_PlatformDisc'].sum()
    g_refunds = df['G_Refunds'].sum()
    g_net = df['G_NetPayout'].sum()

    g_categories = ['Gross', '-Service', '-Packing', '-Discounts', '-Refunds', '=Net']
    g_values = [g_gross, -g_service, -g_pkg, -g_disc, -g_refunds, g_net]

    colors_g = ['green', 'red', 'red', 'red', 'red', 'blue']
    ax2.bar(g_categories, [abs(v) for v in g_values], color=colors_g)
    ax2.set_ylabel('Amount (€)')
    ax2.set_title(f'Glovo Revenue Breakdown\n(Net Margin: {g_net/g_gross*100:.1f}%)', fontweight='bold')
    ax2.set_xticklabels(g_categories, rotation=45, ha='right')

    for i, v in enumerate(g_values):
        ax2.text(i, abs(v) + 500, f'€{abs(v):,.0f}', ha='center', fontsize=8)

    plt.tight_layout()
    plt.savefig(output_dir / 'revenue_waterfall.png', dpi=150)
    plt.close()
    print(f"  ✓ revenue_waterfall.png")

    # 7. Scatter: Orders vs Revenue by Platform
    fig, ax = plt.subplots(figsize=(12, 8))

    ax.scatter(df['D_Orders'], df['D_Gross'], s=100, c=deliveroo_color, alpha=0.7, label='Deliveroo', marker='o')
    ax.scatter(df['G_Orders'], df['G_Gross'], s=100, c=glovo_color, alpha=0.7, label='Glovo', marker='s')

    # Add city labels
    for i, row in df.iterrows():
        if row['D_Orders'] > 0:
            ax.annotate(row['City'], (row['D_Orders'], row['D_Gross']),
                       xytext=(5, 5), textcoords='offset points', fontsize=8, color=deliveroo_color)
        if row['G_Orders'] > 0:
            ax.annotate(row['City'], (row['G_Orders'], row['G_Gross']),
                       xytext=(5, 5), textcoords='offset points', fontsize=8, color=glovo_color)

    ax.set_xlabel('Number of Orders')
    ax.set_ylabel('Gross Revenue (€)')
    ax.set_title('Orders vs Revenue by Platform', fontsize=14, fontweight='bold')
    ax.legend()

    plt.tight_layout()
    plt.savefig(output_dir / 'orders_revenue_scatter.png', dpi=150)
    plt.close()
    print(f"  ✓ orders_revenue_scatter.png")

    # 8. Stacked Bar: Platform Share by City
    fig, ax = plt.subplots(figsize=(14, 7))

    # Calculate percentages
    total_per_city = df['D_Orders'] + df['G_Orders']
    d_pct = df['D_Orders'] / total_per_city * 100
    g_pct = df['G_Orders'] / total_per_city * 100

    ax.barh(cities, d_pct, label='Deliveroo', color=deliveroo_color)
    ax.barh(cities, g_pct, left=d_pct, label='Glovo', color=glovo_color)

    ax.set_xlabel('Market Share (%)')
    ax.set_title('Platform Market Share by City (by Order Volume)', fontsize=14, fontweight='bold')
    ax.legend(loc='lower right')

    # Add percentage labels
    for i, (d, g) in enumerate(zip(d_pct, g_pct)):
        ax.text(d/2, i, f'{d:.0f}%', ha='center', va='center', fontsize=9, fontweight='bold', color='white')
        ax.text(d + g/2, i, f'{g:.0f}%', ha='center', va='center', fontsize=9, fontweight='bold', color='black')

    plt.tight_layout()
    plt.savefig(output_dir / 'market_share_by_city.png', dpi=150)
    plt.close()
    print(f"  ✓ market_share_by_city.png")

    # 9. Summary Dashboard
    fig = plt.figure(figsize=(18, 14))
    gs = fig.add_gridspec(3, 3, hspace=0.35, wspace=0.3)

    # Header metrics
    ax_header = fig.add_subplot(gs[0, :])
    ax_header.axis('off')

    total_d_orders = df['D_Orders'].sum()
    total_g_orders = df['G_Orders'].sum()
    total_d_rev = df['D_Gross'].sum()
    total_g_rev = df['G_Gross'].sum()
    total_d_net = df['D_NetPayout'].sum()
    total_g_net = df['G_NetPayout'].sum()
    d_margin = total_d_net / total_d_rev * 100 if total_d_rev > 0 else 0
    g_margin = total_g_net / total_g_rev * 100 if total_g_rev > 0 else 0

    header_text = f"""
    DELIVEROO vs GLOVO - 9 Italian Stores (Jan 8-14, 2026)

    DELIVEROO: {total_d_orders:,} orders  |  €{total_d_rev:,.2f} revenue  |  {d_margin:.1f}% net margin  |  €{total_d_rev/total_d_orders:.2f} avg basket
    GLOVO: {total_g_orders:,} orders  |  €{total_g_rev:,.2f} revenue  |  {g_margin:.1f}% net margin  |  €{total_g_rev/total_g_orders:.2f} avg basket
    """
    ax_header.text(0.5, 0.5, header_text, transform=ax_header.transAxes,
                   fontsize=13, va='center', ha='center', fontfamily='monospace',
                   bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.3))

    # Orders comparison
    ax1 = fig.add_subplot(gs[1, 0])
    ax1.bar(x - width/2, df['D_Orders'], width, label='Deliveroo', color=deliveroo_color)
    ax1.bar(x + width/2, df['G_Orders'], width, label='Glovo', color=glovo_color)
    ax1.set_title('Orders by Store', fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(cities, rotation=45, ha='right', fontsize=8)
    ax1.legend(fontsize=8)

    # Revenue comparison
    ax2 = fig.add_subplot(gs[1, 1])
    ax2.bar(x - width/2, df['D_Gross'], width, label='Deliveroo', color=deliveroo_color)
    ax2.bar(x + width/2, df['G_Gross'], width, label='Glovo', color=glovo_color)
    ax2.set_title('Revenue (€) by Store', fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(cities, rotation=45, ha='right', fontsize=8)
    ax2.legend(fontsize=8)

    # Margin comparison
    ax3 = fig.add_subplot(gs[1, 2])
    ax3.bar(x - width/2, df['D_NetMargin'], width, label='Deliveroo', color=deliveroo_color)
    ax3.bar(x + width/2, df['G_NetMargin'], width, label='Glovo', color=glovo_color)
    ax3.set_title('Net Margin (%) by Store', fontweight='bold')
    ax3.set_xticks(x)
    ax3.set_xticklabels(cities, rotation=45, ha='right', fontsize=8)
    ax3.legend(fontsize=8)

    # Market share pie - orders
    ax4 = fig.add_subplot(gs[2, 0])
    ax4.pie([total_d_orders, total_g_orders],
            labels=['Deliveroo', 'Glovo'],
            autopct='%1.1f%%',
            colors=[deliveroo_color, glovo_color])
    ax4.set_title('Order Share', fontweight='bold')

    # Market share pie - revenue
    ax5 = fig.add_subplot(gs[2, 1])
    ax5.pie([total_d_rev, total_g_rev],
            labels=['Deliveroo', 'Glovo'],
            autopct='%1.1f%%',
            colors=[deliveroo_color, glovo_color])
    ax5.set_title('Revenue Share', fontweight='bold')

    # Stacked market share
    ax6 = fig.add_subplot(gs[2, 2])
    total_per_city = df['D_Orders'] + df['G_Orders']
    d_pct = df['D_Orders'] / total_per_city * 100
    g_pct = df['G_Orders'] / total_per_city * 100
    ax6.barh(cities, d_pct, color=deliveroo_color, label='Deliveroo')
    ax6.barh(cities, g_pct, left=d_pct, color=glovo_color, label='Glovo')
    ax6.set_xlabel('%')
    ax6.set_title('Share by City', fontweight='bold')
    ax6.legend(fontsize=8, loc='lower right')

    plt.suptitle('Deliveroo vs Glovo - Cross-Platform Comparison Dashboard',
                 fontsize=16, fontweight='bold', y=0.98)
    plt.savefig(output_dir / 'comparison_dashboard.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ comparison_dashboard.png")


def main():
    base_dir = Path(__file__).parent.parent
    csv_path = base_dir / 'data' / 'analysis' / 'platform_comparison.csv'
    output_dir = base_dir / 'data' / 'analysis' / 'charts'

    print("="*60)
    print("GENERATING COMPARISON VISUALIZATIONS")
    print("="*60)

    if not csv_path.exists():
        print(f"Error: {csv_path} not found. Run compare_platforms.py first.")
        return

    print(f"\nReading data from {csv_path.name}")
    create_visualizations(csv_path, output_dir)

    print(f"\n✓ All comparison charts saved to {output_dir}")


if __name__ == "__main__":
    main()
