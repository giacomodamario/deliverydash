# Claude.md - Session Learnings & Context

This file captures learnings, patterns, and context for Claude Code sessions working on this project.

---

## Project Overview

**DeliveryDash** is a multi-platform delivery invoice aggregator for Poke House restaurants. It downloads order/invoice data from Glovo and Deliveroo partner portals using browser automation.

---

## Key Learnings

### 1. Deliveroo Partner Hub

**Login & Session:**
- URL: `https://partner-hub.deliveroo.com/`
- Protected by Cloudflare challenge (~90s to pass, often blocks automation)
- Session saved to `data/sessions/deliveroo_session.json`
- Best approach: Manual Cloudflare pass via VNC, then run script with saved session

**Store Selector (Critical Fix - 2026-01-15):**
- DAC7 tax compliance popup blocks all UI interactions
- Must dismiss via JavaScript: `document.querySelectorAll('.ReactModalPortal').forEach(el => el.innerHTML = '')`
- Store selector button: `[data-testid="pillButtonSiteSelection"]`
- Modal: `[data-testid="siteSelectionModal"]`
- Use `force=True` on clicks to bypass intercepting elements
- 87 total businesses in account (72 Italian S.p.A stores)

**Invoice Structure:**
- CSV format with Italian headers (comma decimal separator)
- Sections: "Orders and related adjustments", "Other payments and fees"
- Key fields: `Valore dell'ordine`, `Commissione Deliveroo`, `Totale da pagare`
- Commission: 25% + 22% VAT = ~30.5% effective rate

**Invoices Page Navigation:**
- Sidebar link: `a:has-text("Fatture")` or `a:has-text("Invoices")`
- Tab: `button:has-text("Synthesis")` or `button:has-text("Sintesi")`
- CSV download: `a:has-text("CSV")`

### 2. Glovo Partner Portal

**Login & Session:**
- URL: `https://partner.glovoapp.com/`
- Protected by PerimeterX (blocks direct API calls with 403)
- Session includes: `accessToken`, `refreshToken`, `px3_cookie`
- Token expires every ~4 hours, keep-alive cron runs every 90 minutes
- Manual login: `glovo_manual_login.py` via VNC

**API Insights:**
- GraphQL endpoint: `vagw-api.eu.prd.portal.restaurant/query`
- Direct HTTP requests fail (PerimeterX), must use browser automation
- Orders CSV export available via UI

**Data Format:**
- 41 columns in orders export
- Key fields: `Subtotal`, `Commission`, `Payout Amount`, `Order status`
- Commission field shows €0 (may be embedded in other fees)
- Net margin: ~88% (vs Deliveroo's 69.5%)

### 3. Browser Automation Patterns

**Patchright (Playwright Fork):**
```python
from patchright.sync_api import sync_playwright
# Stealth features built-in, better for anti-bot bypass
```

**Handling Popups:**
```python
def _dismiss_popups(self):
    # DAC7 modal (no close button)
    self.page.keyboard.press("Escape")
    # Or force remove via JS
    self.page.evaluate("document.querySelectorAll('.ReactModalPortal').forEach(el => el.innerHTML = '')")

    # Cookie consent
    self.page.locator('button:has-text("Accept all")').click()

    # Generic close buttons
    for selector in ['button:has-text("OK")', 'button:has-text("Close")', 'button[aria-label="Close"]']:
        if self.page.locator(selector).is_visible(timeout=1000):
            self.page.locator(selector).click()
```

**Force Click (bypass intercepting elements):**
```python
element.click(force=True)  # Ignores overlay elements
```

**Wait Strategies:**
```python
page.wait_for_load_state("networkidle")
page.wait_for_selector('[data-testid="modal"]', state="visible", timeout=5000)
time.sleep(1)  # Sometimes necessary for React renders
```

### 4. Data Parsing

**European Number Format:**
```python
def parse_european_number(value):
    """Parse '1.234,56' -> 1234.56"""
    if pd.isna(value): return 0.0
    s = str(value).replace('.', '').replace(',', '.')
    return float(s)
```

**Store Mapping (9 Italian Test Stores):**
```python
STORE_MAPPING = {
    'Milano (Brera)': ('Brera', 'Via Broletto'),
    'Brescia': ('Brescia', 'Corso Giuseppe Zanardelli'),
    'Roma': ('Roma Colonna', 'Via Marcantonio Colonna'),
    'Firenze': ('Firenze', 'Piazza degli Ottaviani'),
    'Torino': ('Lingotto', 'Via Santa Croce'),  # Note: Deliveroo uses "Lingotto"
    'Napoli': ('Napoli Chiaia', 'Via Chiaia'),
    'Verona': ('Verona', 'Largo Guido Gonella'),
    'Catania': ('Catania', 'Piazza Giovanni Verga'),
    'Palermo': ('Palermo', 'Via Filippo Pecoraino'),
}
```

### 5. VNC Remote Access

**Start VNC Server:**
```bash
Xvfb :1 -screen 0 1920x1080x24 &
x11vnc -display :1 -forever -shared -rfbport 5901 -localhost no &
```

**Run Browser with Display:**
```bash
DISPLAY=:1 ./venv/bin/python script.py
```

**Connect:** VNC client to `server:5901`

---

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Cloudflare blocks automation | Manual pass via VNC, save session, reuse |
| DAC7 modal blocks clicks | JS remove: `ReactModalPortal.innerHTML = ''` |
| Element click intercepted | Use `force=True` parameter |
| PerimeterX 403 on API | Use browser automation, not direct HTTP |
| Token expired | Run keep-alive cron every 90 min |
| Wrong store selected | Check store selector after navigation |
| CSV download fails (403) | Use click-based download instead of fetch |

---

## File Structure

```
/root/deliverydash/
├── bots/
│   ├── base.py          # BaseBot class with common methods
│   ├── deliveroo.py     # Deliveroo Partner Hub bot
│   ├── glovo.py         # Glovo Partner Portal bot
│   └── glovo_session.py # Glovo token management
├── parsers/
│   ├── base.py          # ParsedOrder, ParsedInvoice dataclasses
│   └── deliveroo.py     # Deliveroo CSV parser
├── analysis/
│   ├── compare_platforms.py    # Cross-platform comparison
│   ├── visualize_comparison.py # Generate charts
│   └── analyze_glovo.py        # Glovo-only analysis
├── data/
│   ├── sessions/        # Saved login sessions (chmod 600)
│   ├── downloads/       # Downloaded CSVs by platform
│   └── analysis/        # Reports and charts
├── config/
│   └── settings.py      # Credentials and config
├── tasks.md             # Status and changelog
└── Claude.md            # This file
```

---

## Metrics Reference (Jan 8-14, 2026)

| Platform | Orders | Revenue | Net Margin | Avg Basket |
|----------|--------|---------|------------|------------|
| Deliveroo | 905 | €17,564 | 69.5% | €19.41 |
| Glovo | 2,152 | €41,827 | 88.0% | €19.44 |

**Market Share:** Glovo 70%, Deliveroo 30%
**Best Deliveroo Market:** Brescia (55% share)
**Worst Deliveroo Market:** Torino (12% share)

---

## Session Commands Cheatsheet

```bash
# Deliveroo - 9 Italian stores
DISPLAY=:1 ./venv/bin/python run_italy_test.py

# Glovo - full sync
DISPLAY=:1 ./venv/bin/python run_platform.py glovo

# Run comparison analysis
./venv/bin/python analysis/compare_platforms.py
./venv/bin/python analysis/visualize_comparison.py

# Check Glovo session
./venv/bin/python -c "from bots.glovo_api import GlovoAPIClient; from pathlib import Path; api = GlovoAPIClient(Path('data/sessions/glovo_session.json')); print(api.get_session_info())"

# Start dashboard
./venv/bin/python -m http.server 8080 --directory dashboard/
```
