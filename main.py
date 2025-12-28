#!/usr/bin/env python3
import sys
import glob
from pathlib import Path
from parsers import parse_invoice


def process_invoices(paths: list):
    files = []
    for path in paths:
        p = Path(path)
        if p.is_file():
            files.append(str(p))
        elif p.is_dir():
            files.extend(glob.glob(str(p / '*.csv')))
            files.extend(glob.glob(str(p / '*.doc')))
            files.extend(glob.glob(str(p / '**/*.csv'), recursive=True))
            files.extend(glob.glob(str(p / '**/*.doc'), recursive=True))

    if not files:
        print("No invoice files found")
        return

    print(f"Found {len(files)} invoice files\n")

    all_orders = []

    for filepath in sorted(set(files)):
        print(f"Processing: {filepath}")
        invoice = parse_invoice(filepath)

        if invoice.errors:
            for err in invoice.errors:
                print(f"  Warning: {err}")

        if invoice.orders:
            print(f"  OK {len(invoice.orders)} orders ({invoice.platform.value})")
            all_orders.extend(invoice.orders)
        else:
            print(f"  X No orders found")

    print(f"\n{'='*50}")
    print(f"SUMMARY: {len(all_orders)} total orders")

    if all_orders:
        total_gross = sum(o.gross_value for o in all_orders)
        total_commission = sum(o.commission_amount for o in all_orders)
        total_net = sum(o.net_payout for o in all_orders)
        print(f"Gross: EUR {total_gross:,.2f}")
        print(f"Commission: EUR {total_commission:,.2f}")
        print(f"Net: EUR {total_net:,.2f}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python main.py <file_or_folder>")
        sys.exit(1)
    process_invoices(sys.argv[1:])
