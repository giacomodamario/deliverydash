# Delivery Platform Analytics Tool

Automated invoice download and analytics for multi-brand delivery operations (Deliveroo, Glovo, Just Eat).

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Copy and configure credentials
cp .env.example .env
# Edit .env with your platform credentials

# Run sync
python main.py sync deliveroo
```

## Commands

```bash
python main.py sync deliveroo    # Download all Deliveroo invoices
python main.py sync glovo        # Download all Glovo invoices
python main.py sync justeat      # Download all Just Eat invoices
python main.py sync all          # Sync all platforms

python main.py status            # Show current status
python main.py report            # Generate report (TODO)
python main.py parse             # Parse downloaded files (TODO)
```

## Project Structure

```
delivery-analytics/
├── bots/               # Platform-specific download bots
│   ├── base.py        # Base bot class with common functionality
│   ├── deliveroo.py   # Deliveroo Partner Hub bot
│   ├── glovo.py       # (TODO) Glovo bot
│   └── justeat.py     # (TODO) Just Eat bot
├── parsers/            # Invoice file parsers
│   └── base.py        # Base parser class
├── storage/            # Database layer
│   └── database.py    # SQLite models and queries
├── reports/            # Report generation
├── config/             # Configuration management
├── downloads/          # Downloaded invoice files (gitignored)
├── data/               # SQLite database (gitignored)
├── main.py            # CLI entry point
└── requirements.txt
```

## Configuration

Set credentials in `.env`:

```env
DELIVEROO_EMAIL=your-email@example.com
DELIVEROO_PASSWORD=your-password
GLOVO_EMAIL=...
JUSTEAT_EMAIL=...
```

## Development Status

- [x] Project structure
- [x] Base bot framework
- [x] Deliveroo bot (login, navigate, download)
- [x] SQLite storage
- [x] CLI interface
- [ ] Glovo bot
- [ ] Just Eat bot
- [ ] Invoice parsers (from Claude.ai session)
- [ ] Report generation
