# Glovo Bot - Tasks & Progress

## Session 2026-01-13 (Evening) - API-First Solution Implemented

### Problem
PerimeterX "press & hold" captcha cannot be bypassed programmatically. All automation attempts (mouse, touch, CDP, xdotool) are detected.

### Solution Implemented: Direct API Access
Instead of fighting the captcha, bypass browser navigation entirely using direct GraphQL API calls with tokens from manual authentication.

### New Files Created
| File | Purpose |
|------|---------|
| `bots/glovo_session.py` | Session/token management - loads, validates, decodes JWT tokens |
| `bots/glovo_api.py` | Direct API client - GraphQL/REST calls with auth headers |

### Files Modified
| File | Changes |
|------|---------|
| `requirements.txt` | Added `requests`, `PyJWT` |
| `bots/__init__.py` | Exports `GlovoSessionManager`, `GlovoAPIClient`, `GlovoSyncService` |
| `glovo_manual_login.py` | Added API verification after login |
| `sync.py` | Added `run_glovo_sync_api()` - uses direct API instead of browser |
| `notifications.py` | Added `send_reauth_needed()` for session expiry alerts |

### How It Works
```
Manual Login (once) → Save Session → API Sync (no captcha) → Auto-refresh tokens
```

1. User runs `python glovo_manual_login.py` on machine with display
2. Manually completes login (captcha + 2FA) in browser
3. Session tokens saved to `data/sessions/glovo_session.json`
4. Subsequent syncs use `GlovoAPIClient` for direct API calls
5. Tokens auto-refresh before expiry (target: every 1-2 weeks manual re-auth)

### Current Session Status
- **Session:** EXPIRED (token expired ~1 hour ago)
- **Stores:** 72 cached from session
- **Action needed:** Run `python glovo_manual_login.py` to create fresh session

### Next Steps
1. Create fresh session via manual login
2. Test API connectivity with valid tokens
3. Discover exact GraphQL query structure via browser network inspection
4. Fine-tune token refresh mechanism based on actual refresh token lifetime

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

## Pending Issues

### Issue: "Tieni premuto" Button Not Found
**Problem:** The press & hold button is a `<P>` element styled as a button, not an actual `<button>` element.

**Current State:**
- Modal detected: ✅
- Button selector finds: ❌ (looking for `<button>`, but it's a `<P>`)

**Debug Info:**
```
Element: <P> class='MuiTypography-root MuiTypography-paragraph-400 muiltr-buxgir'
Parent: <DIV> class='MuiDialogContent-root muiltr-12z3bcr'
Box: {'x': 803, 'y': 537, 'width': 314, 'height': 48}
```

**Fix Needed:**
Update `_handle_press_and_hold()` in `/root/delivery-analytics/bots/glovo.py` to:
1. Look for `p:has-text("Tieni premuto")` or `*:text-is("Tieni premuto")`
2. Or find parent div and use that as click target
3. The bounding box is at x=803, y=537, w=314, h=48

### Issue: Order History Navigation Timeout
**Problem:** The sidebar link clicks timeout after 60 seconds each before falling back to direct URL.

**Logs:**
```
Found Order History link: Storico degli ordini (IT)  [then 60s timeout]
Found Order History link: orders href                 [then 60s timeout]
Found Order History link: Ordini nav                  [then 60s timeout]
Trying direct URL: https://portal.glovoapp.com/dashboard/order-history
```

**Investigation Needed:**
- Why do link clicks timeout?
- Is the page navigation failing silently?

---

## Next Session Tasks

### Priority 1: Create Fresh Session
```bash
cd /root/delivery-analytics
source venv/bin/activate
python glovo_manual_login.py
# Complete login manually in browser (captcha + 2FA)
```

### Priority 2: Discover GraphQL Schema
With valid session, capture actual GraphQL queries:
1. Open Glovo portal in browser with DevTools Network tab
2. Navigate to Order History
3. Copy queries to `vagw-api.eu.prd.portal.restaurant/query`
4. Update `GlovoAPIClient.get_orders()` with actual query structure

### Priority 3: Test Full API Sync
```bash
python run_platform.py glovo
# Should use API client (no browser, no captcha)
```

### Priority 4: Monitor Token Lifetime
- Track how long refresh token stays valid
- Adjust re-auth notification timing accordingly

---

## Key Files

| File | Purpose |
|------|---------|
| `bots/glovo_api.py` | **NEW** - Direct API client (GraphQL/REST) |
| `bots/glovo_session.py` | **NEW** - Session/token management |
| `bots/glovo.py` | Browser-based bot (legacy, may hit captcha) |
| `glovo_manual_login.py` | Manual login script for session bootstrap |
| `sync.py` | Sync orchestration (now uses API by default) |
| `data/sessions/glovo_session.json` | Saved session tokens |

---

## Session Info

- **User:** giovanni.gasparini@pokehouse.it
- **Locations:** 72 (Poke House + Greenbowls)
- **Platform:** GV_IT (Glovo Italy)
- **Session File:** `/root/delivery-analytics/data/sessions/glovo_session.json`

**To get new session:** Use browser, login manually, export storage state to JSON.

---

## API Endpoints Discovered

### Works Without PerimeterX (direct HTTP):
- `vss.eu.restaurant-partners.com` - Store status counts
- `vendor-api-03.eu.restaurant-partners.com` - Availability, recommendations

### Protected by PerimeterX (requires browser):
- `vagw-api.eu.prd.portal.restaurant/query` - GraphQL for orders, reports, finance
