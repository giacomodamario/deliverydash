# Glovo Bot - Tasks & Progress

## Session 2026-01-14 - WORKING

### Current Status: OPERATIONAL
- **Session:** VALID (auto-refreshed via cron)
- **Stores:** 72 (Poke House + Greenbowls)
- **Last sync:** 11,325 orders downloaded successfully
- **Token expiry:** ~4 hours (auto-refreshed every 2 hours)

### How It Works Now
```
Manual Login (once via VNC) → Browser Bot Syncs → Cron Keep-Alive (every 2h)
```

The **browser-based bot** works when session is fresh (no captcha). The **direct API** is blocked by PerimeterX (403).

### Running a Sync
```bash
cd /root/deliverydash
DISPLAY=:1 ./venv/bin/python run_platform.py glovo
```

Or directly:
```bash
DISPLAY=:1 ./venv/bin/python -c "
from bots.glovo import GlovoBot
from datetime import datetime, timedelta

with GlovoBot(email='x', password='x', headless=False) as bot:
    if bot.login():
        invoices = bot.download_invoices(
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now(),
        )
        print(f'Downloaded {len(invoices)} invoice(s)')
"
```

### Automatic Session Keep-Alive
A cron job runs every 2 hours to keep the session alive:

| File | Purpose |
|------|---------|
| `glovo_keepalive.py` | Visits portal to refresh tokens |
| `cron_glovo_keepalive.sh` | Wrapper script for cron |
| `logs/keepalive.log` | Keep-alive execution logs |

**Cron schedule:** `0 */2 * * *` (every 2 hours at :00)

**Check logs:**
```bash
tail -f /root/deliverydash/logs/keepalive.log
```

**Remove cron job:**
```bash
crontab -l | grep -v glovo_keepalive | crontab -
```

### If Session Expires
If the server was down or cron failed, manual re-login is needed:
```bash
cd /root/deliverydash
DISPLAY=:1 ./venv/bin/python glovo_manual_login.py
# Complete login manually in browser (captcha + 2FA)
# Press ENTER when done
```

---

## Session 2026-01-13 (Evening) - API-First Solution (Partial)

### Problem
PerimeterX "press & hold" captcha cannot be bypassed programmatically.

### Solution Attempted: Direct API Access
Created API client to bypass browser, but GraphQL endpoint still returns 403 Forbidden.

### Files Created
| File | Purpose |
|------|---------|
| `bots/glovo_session.py` | Session/token management - loads, validates, decodes JWT tokens |
| `bots/glovo_api.py` | Direct API client - blocked by PerimeterX |
| `glovo_keepalive.py` | **NEW** - Keep-alive script for cron |
| `cron_glovo_keepalive.sh` | **NEW** - Cron wrapper |

### API Status
- **Direct API:** BLOCKED (PerimeterX 403 on GraphQL endpoint)
- **Browser bot:** WORKING (with fresh session)

---

## Session 2026-01-13 (Morning) - Press & Hold Investigation

### Findings
The "Tieni premuto" press & hold challenge is a sophisticated anti-bot verification system:

1. **Button Element Detection Issue (RESOLVED)**
   - The green "Tieni premuto" button IS visible in screenshots
   - BUT it does NOT appear in the DOM when enumerated
   - Only the instruction paragraph `<P>` element is found
   - The actual clickable button might be canvas-based, shadow DOM, or custom component

2. **Position Calculation (WORKING)**
   - Successfully calculating button position based on paragraph and Chiudi button locations
   - Position formula: `y = (para_bottom + chiudi_top) / 2`
   - Screenshots confirm we're clicking in the correct area

3. **Anti-Bot Detection (BLOCKING)**
   - Mouse click with delay: Registers but shows "Riprova" (Retry) - detected as bot
   - Simple press/hold: Same result
   - Touch events: Requires `hasTouch` enabled in browser context
   - The system appears to detect automated interactions

### What We Tried
- ✅ Updated selectors to find P elements
- ✅ Updated modal-gone check for Italian language
- ✅ Added button position calculation fallback
- ✅ Increased wait time for button to render
- ❌ Mouse down/up with 6-8 second hold
- ❌ Playwright click with delay parameter
- ❌ Touch events (requires browser context config)

### Solutions Implemented (2026-01-13 continued)
1. ✅ Enabled `hasTouch: true` in browser context
2. ✅ Running in non-headless mode with Xvfb (`xvfb-run`)
3. ✅ Using CDP touch events (`Input.dispatchTouchEvent`)
4. ✅ Using px-captcha container for button positioning
5. ✅ Updated detection for translation key patterns

### Current Status
- **Detection**: Working - captcha detected via `#px-captcha` and translation keys
- **Positioning**: Working - using px-captcha container bounding box
- **Interaction**: Partially working - CDP touch events reach the element
- **Bypass**: NOT WORKING - PerimeterX still detects automated input

### Recommended Next Steps
1. **CAPTCHA solving service** - Use 2captcha, Anti-Captcha, or similar
2. **Manual one-time solve** - Have user manually solve once per session
3. **Alternative API** - Some endpoints may not require captcha (direct GraphQL)
4. **Browser extension** - Use a real browser with manual captcha solving

---

## Completed Today (2026-01-12)

### 1. Session Management
- [x] Successfully loaded new authenticated session for `giovanni.gasparini@pokehouse.it`
- [x] Session verified working with 72 Poke House locations
- [x] Token expires in ~2 hours from session creation

### 2. Reliability Improvements Implemented
- [x] **Automatic Token Refresh** (`get_token_expiry_minutes()`, `refresh_token_if_needed()`)
  - Decodes JWT to check expiry time
  - Triggers browser-based refresh if < 30 min remaining
  - Saves refreshed session automatically

- [x] **PerimeterX Detection** (`is_perimeterx_blocked()`, `handle_perimeterx_block()`)
  - Detects block signatures (`"blockScript":`, captcha URLs, etc.)
  - Checks for dashboard elements first to avoid false positives
  - Clears cookies and re-authenticates on block

- [x] **Integrated into Login Flow**
  - Reports token expiry at start
  - Checks for PerimeterX blocks after navigation
  - Auto-recovers from blocks

### 3. Press & Hold Challenge
- [x] Added Italian language support ("Tieni premuto", "Prima di continuare")
- [x] Added challenge handling after order history navigation
- [x] Challenge detected and attempted

---

## Resolved Issues

### ✅ "Tieni premuto" Captcha
**Solution:** Use browser-based bot with manual login session. Captcha only appears on fresh logins, not when using saved session.

### ✅ Session Expiry
**Solution:** Cron job runs `glovo_keepalive.py` every 2 hours to refresh the session automatically.

---

## Future Improvements (Optional)

### Discover GraphQL Schema
To enable direct API access (faster, no browser needed):
1. Open Glovo portal in browser with DevTools Network tab
2. Navigate to Order History, capture GraphQL queries
3. Update `GlovoAPIClient.get_orders()` with actual query structure
4. Find way to bypass PerimeterX on API endpoint

---

## Key Files

| File | Purpose |
|------|---------|
| `bots/glovo.py` | Browser-based bot - **PRIMARY** (works with fresh session) |
| `bots/glovo_session.py` | Session/token management |
| `bots/glovo_api.py` | Direct API client (blocked by PerimeterX) |
| `glovo_manual_login.py` | Manual login script for session bootstrap |
| `glovo_keepalive.py` | Keep-alive script (cron runs every 2h) |
| `cron_glovo_keepalive.sh` | Cron wrapper script |
| `data/sessions/glovo_session.json` | Saved session tokens |
| `logs/keepalive.log` | Keep-alive execution logs |

---

## Session Info

- **User:** giovanni.gasparini@pokehouse.it
- **Locations:** 72 (Poke House + Greenbowls)
- **Platform:** GV_IT (Glovo Italy)
- **Session File:** `/root/deliverydash/data/sessions/glovo_session.json`

**To get new session:**
```bash
DISPLAY=:1 ./venv/bin/python glovo_manual_login.py
```

---

## API Endpoints Discovered

### Works Without PerimeterX (direct HTTP):
- `vss.eu.restaurant-partners.com` - Store status counts
- `vendor-api-03.eu.restaurant-partners.com` - Availability, recommendations

### Protected by PerimeterX (requires browser):
- `vagw-api.eu.prd.portal.restaurant/query` - GraphQL for orders, reports, finance
