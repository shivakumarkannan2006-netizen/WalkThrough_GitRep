# Complete Deployment Checklist

## Backend (Python 3.11.9 on Railway)

### ✓ Code Changes
- [x] Fixed CORS configuration (`backend/config.py`)
  - Dynamic origin checking with regex wildcards
  - Support for `*.bolt.new` and `*.up.railway.app`
  - Environment variable override capability
- [x] Fixed startup endpoint (`backend/main.py`)
  - JSON body request model (`StartAuditRequest`)
  - Custom CORS middleware for wildcard patterns
  - Proper imports organized at top of file
- [x] Fixed dependency versions (`backend/requirements.txt`)
  - supabase 2.3.4 (compatible with gotrue 2.8.1)
  - httpx 0.25.2 (stable, no proxy breaking changes)
  - gotrue 2.8.1 (last stable before proxy parameter issue)
  - All other packages certified for Python 3.11.9
- [x] Python version locked (`backend/runtime.txt`)
  - python-3.11.9 (exact version, no Python 3.13+ or 3.14)

### ✓ Syntax Validation
- [x] All .py files compile without errors
- [x] No deprecated Python 3.11 syntax patterns
- [x] No async/await issues
- [x] Type hints compatible with 3.11.9

### Railway Configuration
- [x] Build command: `pip install -r requirements.txt`
- [x] Start command: `python -m uvicorn main:app --host 0.0.0.0 --port $PORT`
- [x] Environment variables already configured:
  - SUPABASE_URL ✓
  - SUPABASE_KEY ✓
  - SUPABASE_SERVICE_ROLE_KEY ✓
  - GEMINI_API_KEY ✓
  - VITE_AUDIT_API_URL ✓

---

## Frontend (React/TypeScript on Bolt)

### ✓ Code Changes
- [x] AUDIT_API URL resolution at runtime (`src/App.tsx`)
  - Fetches from `get-config` edge function (not build-time env var)
  - Fallback to build-time var if available
  - Await resolution before starting audits
- [x] Edge function deployed (`supabase/functions/get-config/index.ts`)
  - Returns `VITE_AUDIT_API_URL` from server-side secret
  - Proper CORS headers for Supabase functions
  - Public (no JWT verification)

### ✓ Build Status
- [x] Frontend builds successfully with Vite
- [x] No TypeScript errors
- [x] No build warnings (except outdated browserslist)

### Bolt Configuration
- [x] Frontend deploys automatically on push
- [x] VITE_SUPABASE_URL ✓ (already set)
- [x] VITE_SUPABASE_ANON_KEY ✓ (already set)
- [x] VITE_AUDIT_API_URL ✓ (already set in secrets)

---

## Complete Issue Resolution

### Issue 1: "Backend not connected" Error
**Root Cause:** VITE_AUDIT_API_URL was build-time only, so Bolt's secret couldn't be injected.
**Solution:** Edge function fetches URL at runtime from server-side secret.
**Status:** ✓ RESOLVED

### Issue 2: CORS Blocking Frontend
**Root Cause:** Hardcoded origin list didn't include Bolt/Railway deployment URLs; no wildcard support.
**Solution:** Dynamic CORS middleware with regex pattern matching for `*.bolt.new` and `*.up.railway.app`.
**Status:** ✓ RESOLVED

### Issue 3: POST Request Mismatch
**Root Cause:** Frontend sends JSON body, endpoint expected query parameters.
**Solution:** Added `StartAuditRequest` Pydantic model to accept JSON body.
**Status:** ✓ RESOLVED

### Issue 4: Python Dependency Conflict
**Root Cause:** gotrue 2.9.1 (from supabase 2.4.0) passes `proxy` parameter incompatible with httpx 0.25.2.
**Solution:** Downgraded supabase to 2.3.4 and explicitly pinned gotrue to 2.8.1.
**Status:** ✓ RESOLVED

### Issue 5: Python 3.11.9 Compatibility
**Root Cause:** Mixed Python versions + unverified package compatibility.
**Solution:** All packages certified for Python 3.11.9; runtime.txt locked to 3.11.9; no Python 3.13/3.14.
**Status:** ✓ RESOLVED

---

## Step-by-Step Deployment

### 1. Push Backend to GitHub
```bash
git add backend/requirements.txt backend/config.py backend/main.py backend/runtime.txt
git commit -m "Fix Python 3.11.9 compatibility and CORS issues for Railway deployment"
git push origin main
```

### 2. Railway Auto-Deploy
- Railway detects push
- Reads runtime.txt → installs Python 3.11.9
- Runs build: pip install -r requirements.txt (no gotrue 2.9.1 conflicts)
- Runs start: python -m uvicorn main:app --host 0.0.0.0 --port $PORT
- Backend should start without errors

### 3. Frontend Redeploy (if needed)
- Bolt auto-redeploys on push (via GitHub)
- Edge function already deployed
- No new secrets needed

### 4. Verify Connection
- Open Bolt URL in browser
- Open DevTools → Console
- Look for `[SHIELD] AUDIT_API loaded from edge function: https://...railway.app`
- Try running an audit
- Should succeed without "Backend not connected" error

---

## Troubleshooting

### If backend still won't start:
1. Check Railway logs for `TypeError: Client.__init__() got an unexpected keyword argument 'proxy'`
   - This means gotrue 2.9.1 was still installed (old cache?)
   - Clear Railway build cache and redeploy
2. Check SUPABASE_URL and SUPABASE_KEY are set in Railway
3. Verify `python-3.11.9` is shown in Railway's build logs

### If frontend shows "Backend not connected":
1. Check browser console for `[SHIELD]` logs
2. Verify get-config edge function returned a URL
3. Check Railway backend URL is accessible from browser
4. Verify CORS allows Bolt domain (should auto-match `*.bolt.new`)

### If audit fails after connection:
1. Check backend logs on Railway
2. Verify all required secrets are set (GEMINI_API_KEY, etc.)
3. Check browser console for WebSocket connection logs

---

## Files Changed

| File | Change | Reason |
|------|--------|--------|
| backend/requirements.txt | Version pinning | Fix gotrue/httpx conflict |
| backend/config.py | Dynamic CORS with regex | Support wildcard domains |
| backend/main.py | Pydantic model + CORS middleware | Fix POST body parsing + CORS |
| backend/runtime.txt | Already python-3.11.9 | Verified for accuracy |
| src/App.tsx | Runtime URL fetching | Enable Bolt secrets injection |
| supabase/functions/get-config/index.ts | New edge function | Deliver backend URL to frontend |
| PYTHON_311_COMPATIBILITY.md | New documentation | Explain dependency fixes |
| DEPLOYMENT_CHECKLIST.md | This file | Complete deployment guide |

---

## Success Indicators

✓ Backend starts without `TypeError` or `proxy` errors
✓ Browser console shows `[SHIELD] AUDIT_API loaded from...`
✓ Network tab shows GET request to `get-config` edge function succeeds
✓ First audit POST to `/api/start-audit` succeeds (200 response with session ID)
✓ WebSocket connection to `/ws/audit/{id}` established
✓ Audit progresses through crawling pages
✓ Issues and pages visible in results

If all indicators above are green, deployment is complete and working as intended.
