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

**Schedule:** `0 */2 * * *` (every 2 hours at :00)

**View crontab:**
```bash
crontab -l
```

**Remove cron job:**
```bash
crontab -l | grep -v glovo_keepalive | crontab -
```

**Re-add cron job:**
```bash
(crontab -l 2>/dev/null; echo "0 */2 * * * /root/deliverydash/cron_glovo_keepalive.sh") | crontab -
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

## Changelog

### 2026-01-14
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
