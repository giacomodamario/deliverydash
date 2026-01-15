# Glovo Bot - Status & Usage

## Current Status: OPERATIONAL

- **Session:** VALID (auto-refreshed via cron every 2 hours)
- **Stores:** 72 (Poke House + Greenbowls)
- **User:** giovanni.gasparini@pokehouse.it
- **Platform:** GV_IT (Glovo Italy)

---

## Quick Reference

### Run a Sync
```bash
cd /root/deliverydash
DISPLAY=:1 ./venv/bin/python run_platform.py glovo
```

### Check Session Status
```bash
./venv/bin/python -c "
from bots.glovo_api import GlovoAPIClient
from pathlib import Path
api = GlovoAPIClient(Path('data/sessions/glovo_session.json'))
info = api.get_session_info()
print(f'Valid: {info[\"valid\"]}, Expires in: {info[\"token_expiry_minutes\"]:.0f} min')
"
```

### Check Keep-Alive Logs
```bash
tail -f /root/deliverydash/logs/keepalive.log
```

### Manual Re-Login (if session expires)
```bash
cd /root/deliverydash
DISPLAY=:1 ./venv/bin/python glovo_manual_login.py
# Complete login in browser (captcha + 2FA)
# Press ENTER when done
```

---

## How It Works

```
Manual Login (once via VNC) → Browser Bot Syncs → Cron Keep-Alive (every 2h)
```

1. **Manual login** solves the PerimeterX captcha once
2. **Session saved** to `data/sessions/glovo_session.json`
3. **Browser bot** uses saved session (no captcha needed)
4. **Cron job** refreshes session every 2 hours to prevent expiry

### Why Not Direct API?
The GraphQL endpoint (`vagw-api.eu.prd.portal.restaurant/query`) is protected by PerimeterX and returns 403 Forbidden for direct HTTP requests. Browser automation with a valid session bypasses this.

---

## Key Files

| File | Purpose |
|------|---------|
| `bots/glovo.py` | Browser-based bot (primary) |
| `bots/glovo_session.py` | Session/token management |
| `bots/glovo_api.py` | API client (session validation only) |
| `glovo_manual_login.py` | Manual login for session bootstrap |
| `glovo_keepalive.py` | Keep-alive script (cron) |
| `cron_glovo_keepalive.sh` | Cron wrapper |
| `data/sessions/glovo_session.json` | Saved session tokens |
| `logs/keepalive.log` | Keep-alive logs |

---

## Cron Configuration

**Schedule:** Every 90 minutes (two cron lines):
```
0 0,3,6,9,12,15,18,21 * * *
30 1,4,7,10,13,16,19,22 * * *
```

**View crontab:**
```bash
crontab -l
```

**Remove cron job:**
```bash
crontab -l | grep -v glovo_keepalive | crontab -
```

**Re-add cron job (90 min interval):**
```bash
(crontab -l 2>/dev/null | grep -v glovo_keepalive; echo "0 0,3,6,9,12,15,18,21 * * * /root/deliverydash/cron_glovo_keepalive.sh"; echo "30 1,4,7,10,13,16,19,22 * * * /root/deliverydash/cron_glovo_keepalive.sh") | crontab -
```

---

## Configuration

### Enable Debug Screenshots
Edit `config/settings.py`:
```python
debug_screenshots: bool = True  # Default: False
```

### Session File Permissions
Session files are chmod 600 (owner-only) for security.

---

---

# Deliveroo Bot - Status & Tasks

## Current Status: IN PROGRESS

### Completed (2026-01-14)
- [x] Updated credentials to new account (`giacomo@techfoodies.it`)
- [x] Implemented date filtering (`--last-week`, `--start-date`, `--end-date`)
- [x] Fixed date extraction from invoice table (Deliveroo uses custom `div[class*="TableRow"]` not `<tr>`)
- [x] `--last-week` now uses Mon-Sun calendar weeks
- [x] Updated `run_platform.py` CLI with date range options
- [x] Updated `bots/base.py` to pass date params to `download_invoices()`

### Completed (2026-01-15)
- [x] **Multi-location/company detection** - Working! Detects 87 businesses
  - Opens Filter Sites modal via `button:has-text("store")`
  - Extracts business IDs from radio button values
  - Clicks "Select" button to apply filter
  - Iterates through all businesses, downloading invoices for each

### Completed (2026-01-15 - Cross-Platform Analysis)
- [x] **Downloaded 9 Italian store invoices** via VNC + manual Cloudflare pass
  - Brera, Brescia, Catania, Firenze, Napoli Chiaia, Palermo, Roma Colonna, Torino, Verona
  - 905 orders, €17,563.64 gross revenue
- [x] **Cross-platform comparison: Deliveroo vs Glovo**
  - Glovo: 2,152 orders, €41,827 revenue, 88% net margin
  - Deliveroo: 905 orders, €17,564 revenue, 69.5% net margin
  - Glovo has 2.4x more orders and 18.5pp better margins
- [x] **Generated visualizations** (9 charts in `data/analysis/charts/`)
- [x] **Created comparison report** (`data/analysis/comparison_report.md`)

### To Do
- [ ] Automate Cloudflare bypass for Deliveroo (currently requires manual VNC)
- [ ] Set up scheduled sync for both platforms

### Usage
```bash
# Last week (Mon-Sun)
./venv/bin/python run_platform.py deliveroo --last-week --visible

# Custom date range
./venv/bin/python run_platform.py deliveroo --start-date 2026-01-01 --end-date 2026-01-14

# Quick sync (5 newest invoices)
./venv/bin/python run_platform.py deliveroo
```

### Notes
- Cloudflare challenge takes ~90s to pass (or times out)
- Date filtering works: stops when finding invoices older than start_date
- Invoice dates extracted from table rows (format: "5 Jan 2026")

---

## Changelog

### 2026-01-15
- Fixed keep-alive cron: changed from 2h to 90min interval (token was expiring before refresh)
- Fixed `glovo_manual_login.py`: detection now checks localStorage `isAuthenticated` instead of URL
- Fixed VNC server: now listens on all interfaces (`-localhost no`) for remote access
- **Deliveroo multi-location support completed:**
  - Fixed `_switch_to_branch()` to navigate to main dashboard before opening modal
  - Fixed modal button: uses "Select" instead of "Apply/Filter"
  - Successfully iterates through 87 businesses, downloading invoices for each

### 2026-01-14
- Added Deliveroo account (giacomo@techfoodies.it)
- Implemented date filtering for Deliveroo bot
- Fixed invoice table row detection (div-based, not tr-based)
- Started multi-location support (dropdown detection in progress)
- Code cleanup: removed 968 lines of dead code
- Simplified `_handle_press_and_hold()` (was 600 lines, now 25)
- Removed unused GraphQL methods from `glovo_api.py`
- Added `debug_screenshots` setting (disabled by default)
- Set session file permissions to 600
- Added keep-alive cron job

### 2026-01-13
- Implemented session-based login (bypasses captcha)
- Created `glovo_session.py` for token management
- Discovered PerimeterX blocks direct API access

### 2026-01-12
- Initial Glovo bot implementation
- Added PerimeterX detection and handling
- Added token expiry monitoring
