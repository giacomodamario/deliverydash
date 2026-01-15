#!/usr/bin/env python3
"""Run Deliveroo sync for 10 Italian test locations only."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from config.logging import setup_logging
from bots import DeliverooBot

# Italian locations to test (9 stores, excluding Genova)
# Pattern matching: look for these keywords in location names
ITALY_TEST_PATTERNS = [
    "Brera",           # Milano
    "Firenze",         # Firenze
    "Roma Colonna",    # Roma
    "Torino",          # Torino
    "Napoli Chiaia",   # Napoli
    "Brescia",         # Brescia
    "Verona",          # Verona
    "Catania",         # Catania
    "Palermo",         # Palermo
]

def main():
    setup_logging()

    print("\n" + "="*60)
    print("DELIVEROO - ITALY TEST (9 locations)")
    print("="*60)
    print(f"Email: {settings.deliveroo.email}")
    print(f"Locations: {len(ITALY_TEST_PATTERNS)}")
    print("="*60 + "\n")

    settings.ensure_directories()

    with DeliverooBot(
        email=settings.deliveroo.email,
        password=settings.deliveroo.password,
        headless=False,
    ) as bot:
        if not bot.login():
            print("Login failed!")
            return

        # Get all locations and filter for Italy
        all_locations = bot.get_locations()
        print(f"\nTotal locations: {len(all_locations)}")

        # Filter for our test locations using pattern matching
        italy_locations = []
        matched_patterns = set()
        for loc in all_locations:
            name = loc.get("name", "")
            for pattern in ITALY_TEST_PATTERNS:
                if pattern.lower() in name.lower() and pattern not in matched_patterns:
                    italy_locations.append(loc)
                    matched_patterns.add(pattern)
                    print(f"  ✓ {name} (matched: {pattern})")
                    break

        print(f"\nMatched {len(italy_locations)} Italian test locations")

        # Download 1 invoice per location
        all_invoices = []
        for i, location in enumerate(italy_locations, 1):
            print(f"\n[{i}/{len(italy_locations)}] {location['name']}")
            invoices = bot.download_invoices(
                location_id=location["id"],
                max_invoices=1,
            )
            all_invoices.extend(invoices)
            print(f"  Downloaded {len(invoices)} invoice(s)")

        print(f"\n{'='*60}")
        print(f"COMPLETE: Downloaded {len(all_invoices)} invoices from {len(italy_locations)} locations")
        print("="*60)

if __name__ == "__main__":
    main()
