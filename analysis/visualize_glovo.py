#!/usr/bin/env python3
"""
Generate visualizations for Glovo 9 Italian stores analysis.
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
    """Create all visualizations from the analysis CSV."""

    df = pd.read_csv(csv_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Set style
    plt.style.use('seaborn-v0_8-whitegrid')
    colors = ['#00A884', '#FF6B35', '#004E98', '#FFD700', '#7B2D8E',
              '#E63946', '#2A9D8F', '#264653', '#E9C46A']

    # 1. Order Volume by Store
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.barh(df['City'], df['Orders'], color=colors[:len(df)])
    ax.set_xlabel('Number of Orders')
    ax.set_title('Glovo Order Volume by Store (Jan 8-14, 2026)', fontsize=14, fontweight='bold')
    ax.bar_label(bars, padding=3)
    plt.tight_layout()
    plt.savefig(output_dir / 'orders_by_store.png', dpi=150)
    plt.close()
    print(f"  ✓ orders_by_store.png")

    # 2. Revenue by Store
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.barh(df['City'], df['Gross Revenue'], color=colors[:len(df)])
    ax.set_xlabel('Gross Revenue (€)')
    ax.set_title('Glovo Revenue by Store (Jan 8-14, 2026)', fontsize=14, fontweight='bold')
    ax.bar_label(bars, fmt='€%.0f', padding=3)
    plt.tight_layout()
    plt.savefig(output_dir / 'revenue_by_store.png', dpi=150)
    plt.close()
    print(f"  ✓ revenue_by_store.png")

    # 3. Average Basket Size
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.barh(df['City'], df['Avg Basket Size'], color=colors[:len(df)])
    ax.set_xlabel('Average Basket Size (€)')
    ax.set_title('Glovo Average Basket Size by Store', fontsize=14, fontweight='bold')
    ax.bar_label(bars, fmt='€%.2f', padding=3)
    ax.axvline(df['Avg Basket Size'].mean(), color='red', linestyle='--', label=f'Avg: €{df["Avg Basket Size"].mean():.2f}')
    ax.legend()
    plt.tight_layout()
    plt.savefig(output_dir / 'basket_size.png', dpi=150)
    plt.close()
    print(f"  ✓ basket_size.png")

    # 4. Net Margin by Store
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.barh(df['City'], df['Net Margin %'], color=colors[:len(df)])
    ax.set_xlabel('Net Margin (%)')
    ax.set_title('Glovo Net Margin by Store', fontsize=14, fontweight='bold')
    ax.bar_label(bars, fmt='%.1f%%', padding=3)
    ax.axvline(df['Net Margin %'].mean(), color='red', linestyle='--', label=f'Avg: {df["Net Margin %"].mean():.1f}%')
    ax.legend()
    plt.tight_layout()
    plt.savefig(output_dir / 'net_margin.png', dpi=150)
    plt.close()
    print(f"  ✓ net_margin.png")

    # 5. Pie Chart - Order Distribution
    fig, ax = plt.subplots(figsize=(10, 10))
    wedges, texts, autotexts = ax.pie(
        df['Orders'],
        labels=df['City'],
        autopct='%1.1f%%',
        colors=colors[:len(df)],
        pctdistance=0.75,
        startangle=90
    )
    ax.set_title('Order Distribution by Store', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_dir / 'order_distribution.png', dpi=150)
    plt.close()
    print(f"  ✓ order_distribution.png")

    # 6. Revenue Breakdown (Stacked Bar)
    fig, ax = plt.subplots(figsize=(14, 8))

    # Calculate components
    width = 0.6
    x = np.arange(len(df))

    # Net Payout (bottom)
    net = df['Net Payout'].values
    # Discounts
    disc = df['Total Discounts'].values
    # Vendor Charges
    charges = df['Vendor Charges'].values
    # Remaining (fees, refunds, etc.)
    remaining = df['Gross Revenue'].values - net - disc - charges

    ax.bar(x, net, width, label='Net Payout', color='#00A884')
    ax.bar(x, disc, width, bottom=net, label='Discounts', color='#FFD700')
    ax.bar(x, charges, width, bottom=net+disc, label='Vendor Charges', color='#FF6B35')
    ax.bar(x, remaining, width, bottom=net+disc+charges, label='Other Deductions', color='#E63946')

    ax.set_ylabel('Revenue (€)')
    ax.set_title('Revenue Breakdown by Store', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(df['City'], rotation=45, ha='right')
    ax.legend(loc='upper right')
    plt.tight_layout()
    plt.savefig(output_dir / 'revenue_breakdown.png', dpi=150)
    plt.close()
    print(f"  ✓ revenue_breakdown.png")

    # 7. Scatter Plot - Orders vs Revenue
    fig, ax = plt.subplots(figsize=(10, 8))
    scatter = ax.scatter(df['Orders'], df['Gross Revenue'],
                         s=df['Avg Basket Size']*20,
                         c=df['Net Margin %'],
                         cmap='RdYlGn',
                         alpha=0.7)

    # Add labels
    for i, row in df.iterrows():
        ax.annotate(row['City'], (row['Orders'], row['Gross Revenue']),
                   xytext=(5, 5), textcoords='offset points', fontsize=9)

    ax.set_xlabel('Number of Orders')
    ax.set_ylabel('Gross Revenue (€)')
    ax.set_title('Orders vs Revenue (bubble size = basket, color = margin)', fontsize=12, fontweight='bold')

    cbar = plt.colorbar(scatter)
    cbar.set_label('Net Margin %')

    plt.tight_layout()
    plt.savefig(output_dir / 'orders_vs_revenue.png', dpi=150)
    plt.close()
    print(f"  ✓ orders_vs_revenue.png")

    # 8. Discount Analysis
    fig, ax = plt.subplots(figsize=(12, 6))

    df_sorted = df.sort_values('Total Discounts', ascending=True)

    bars = ax.barh(df_sorted['City'], df_sorted['Total Discounts'], color='#FFD700')
    ax.set_xlabel('Total Discounts (€)')
    ax.set_title('Vendor-Funded Discounts by Store', fontsize=14, fontweight='bold')
    ax.bar_label(bars, fmt='€%.2f', padding=3)

    # Add percentage labels
    for i, (city, total, gross) in enumerate(zip(df_sorted['City'], df_sorted['Total Discounts'], df_sorted['Gross Revenue'])):
        pct = (total / gross * 100) if gross > 0 else 0
        ax.annotate(f'({pct:.1f}%)', xy=(total + 5, i), va='center', fontsize=9, color='gray')

    plt.tight_layout()
    plt.savefig(output_dir / 'discounts.png', dpi=150)
    plt.close()
    print(f"  ✓ discounts.png")

    # 9. Summary Dashboard
    fig = plt.figure(figsize=(16, 12))

    # Create grid
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

    # Total metrics boxes
    ax_totals = fig.add_subplot(gs[0, :])
    ax_totals.axis('off')

    total_orders = df['Orders'].sum()
    total_revenue = df['Gross Revenue'].sum()
    avg_basket = df['Avg Basket Size'].mean()
    avg_margin = df['Net Margin %'].mean()

    metrics_text = f"""
    GLOVO - 9 Italian Stores Summary (Jan 8-14, 2026)

    Total Orders: {total_orders:,}        |        Total Revenue: €{total_revenue:,.2f}        |        Avg Basket: €{avg_basket:.2f}        |        Avg Margin: {avg_margin:.1f}%
    """
    ax_totals.text(0.5, 0.5, metrics_text, transform=ax_totals.transAxes,
                  fontsize=14, va='center', ha='center',
                  bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.3))

    # Orders chart
    ax1 = fig.add_subplot(gs[1, 0])
    ax1.barh(df['City'], df['Orders'], color=colors[:len(df)])
    ax1.set_title('Orders', fontweight='bold')
    ax1.set_xlabel('Count')

    # Revenue chart
    ax2 = fig.add_subplot(gs[1, 1])
    ax2.barh(df['City'], df['Gross Revenue'], color=colors[:len(df)])
    ax2.set_title('Revenue (€)', fontweight='bold')
    ax2.set_xlabel('€')

    # Margin chart
    ax3 = fig.add_subplot(gs[1, 2])
    ax3.barh(df['City'], df['Net Margin %'], color=colors[:len(df)])
    ax3.set_title('Net Margin (%)', fontweight='bold')
    ax3.set_xlabel('%')

    # Pie chart
    ax4 = fig.add_subplot(gs[2, 0])
    ax4.pie(df['Orders'], labels=df['City'], autopct='%1.0f%%',
            colors=colors[:len(df)], textprops={'fontsize': 8})
    ax4.set_title('Order Share', fontweight='bold')

    # Basket size
    ax5 = fig.add_subplot(gs[2, 1])
    ax5.barh(df['City'], df['Avg Basket Size'], color=colors[:len(df)])
    ax5.axvline(avg_basket, color='red', linestyle='--', alpha=0.7)
    ax5.set_title('Avg Basket (€)', fontweight='bold')
    ax5.set_xlabel('€')

    # Discounts
    ax6 = fig.add_subplot(gs[2, 2])
    ax6.barh(df['City'], df['Total Discounts'], color='#FFD700')
    ax6.set_title('Discounts (€)', fontweight='bold')
    ax6.set_xlabel('€')

    plt.suptitle('Glovo Performance Dashboard', fontsize=16, fontweight='bold', y=0.98)
    plt.savefig(output_dir / 'dashboard.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ dashboard.png")


def main():
    base_dir = Path(__file__).parent.parent
    csv_path = base_dir / 'data' / 'analysis' / 'glovo_analysis.csv'
    output_dir = base_dir / 'data' / 'analysis' / 'charts'

    print("="*60)
    print("GENERATING VISUALIZATIONS")
    print("="*60)

    if not csv_path.exists():
        print(f"Error: {csv_path} not found. Run analyze_glovo.py first.")
        return

    print(f"\nReading data from {csv_path.name}")
    create_visualizations(csv_path, output_dir)

    print(f"\n✓ All charts saved to {output_dir}")


if __name__ == "__main__":
    main()
