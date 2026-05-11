# Lessons Learned - Complete Project Issues & Fixes

## Overview

This document catalogs all issues discovered during development and deployment. It serves as a reference to prevent similar issues in future development.

---

## 1. Python 3.11.9 Compatibility Issues

### Issue: Gotrue 2.9.1 + Httpx 0.25.2 Conflict
**Severity:** CRITICAL - Prevents app startup
**Error:** `TypeError: Client.__init__() got an unexpected keyword argument 'proxy'`

**Root Cause:**
- Supabase 2.4.0 → pulls gotrue 2.9.1
- Gotrue 2.9.1 changed proxy parameter handling
- Httpx 0.25.2 doesn't accept the `proxy` parameter in the way gotrue 2.9.1 tries to pass it
- Version incompatibility between transitive dependencies

**Solution:**
- Downgraded supabase from 2.4.0 → 2.3.4
- Explicitly pinned gotrue to 2.8.1 (last stable before proxy change)
- All package versions certified for Python 3.11.9

**Prevention:**
- Always pin transitive dependency versions when known conflicts exist
- Test dependency chains in local environment before deployment
- Check GitHub issues for known version conflicts between packages

**Files Changed:**
- `backend/requirements.txt` - pinned all versions
- `PYTHON_311_COMPATIBILITY.md` - comprehensive compatibility matrix

---

## 2. CORS & Frontend-Backend Communication Issues

### Issue: Hardcoded Origin Whitelist
**Severity:** HIGH - Blocks frontend from calling backend
**Error:** CORS error in browser console; 403 Forbidden from backend

**Root Cause:**
- CORS allowed origins hardcoded to localhost only
- Didn't account for Bolt.new deployment URLs or Railway backend URLs
- No wildcard support for dynamic domains

**Solution:**
- Created dynamic CORS middleware with regex pattern matching
- Added support for `*.bolt.new` and `*.up.railway.app` patterns
- Allow CORS_ORIGINS override via environment variable

**Prevention:**
- Never hardcode domain whitelists
- Always support wildcard patterns for development/staging domains
- Use environment variables for domain lists

**Files Changed:**
- `backend/config.py` - dynamic CORS with function wrapper
- `backend/main.py` - custom CORS middleware with regex matching

---

### Issue: VITE_AUDIT_API_URL Build-Time Injection
**Severity:** HIGH - Frontend can't find backend
**Error:** Frontend shows "Backend not connected"; VITE_AUDIT_API_URL = (not set)

**Root Cause:**
- Vite bakes environment variables at build time
- Bolt's secrets aren't available during build process
- Frontend couldn't dynamically discover backend URL

**Solution:**
- Created Supabase edge function (`get-config`) that serves backend URL
- Frontend fetches URL from edge function at runtime (not build time)
- Backend URL stored in Supabase secret, injected via edge function

**Prevention:**
- Never rely on build-time environment variables for runtime configuration
- Use runtime configuration injection for deployment-specific values
- For Bolt/Railway, leverage Supabase edge functions for dynamic config delivery

**Files Changed:**
- `src/App.tsx` - added runtime config fetching
- `supabase/functions/get-config/index.ts` - new edge function

---

## 3. API Contract Issues

### Issue: POST Body vs Query Parameter Mismatch
**Severity:** MEDIUM - API endpoint fails silently
**Error:** `/api/start-audit` returns 422 Unprocessable Entity

**Root Cause:**
- Frontend sends: `POST /api/start-audit` with JSON body
- Backend endpoint declared: query parameters (not body parsing)
- FastAPI parsed body as query params, failed validation

**Solution:**
- Created `StartAuditRequest` Pydantic model
- Changed endpoint to accept JSON body, not query parameters
- Explicit type validation with automatic documentation

**Prevention:**
- Frontend and backend must agree on request format BEFORE coding
- Use OpenAPI/Swagger documentation to define contracts
- Test API contracts with actual payloads, not mock data

**Files Changed:**
- `backend/main.py` - added StartAuditRequest model and body parsing

---

## 4. Railway 502 Bad Gateway Issues

### Issue: Module-Level Initialization Crash
**Severity:** CRITICAL - 502 Bad Gateway on all requests
**Error:** Railway logs show: `supabase = init_supabase()` crashes at import time

**Root Cause:**
- `supabase = init_supabase()` at module level (line 101 of main.py)
- When Railway runs `python -m uvicorn main:app`, it imports main.py
- If any module-level code crashes, the app import fails
- Uvicorn has no app to run → 502 Bad Gateway

**Solution:**
- Moved initialization from module level to `lifespan()` startup handler
- Wrapped in try/catch with detailed error logging
- App now returns meaningful 503 during startup instead of crashing

**Prevention:**
- RULE: Never initialize expensive resources at module level
- RULE: Move all initialization to `@asynccontextmanager` lifespan
- RULE: Test import with: `python -c "from main import app; print('OK')"`

**Files Changed:**
- `backend/main.py` - moved supabase init to lifespan
- `backend/db.py` - added error handling and logging

---

### Issue: Incomplete Port Binding Configuration
**Severity:** HIGH - May cause 502 in certain deployment scenarios
**Error:** App binds to port 8000 locally but Railway assigns dynamic port

**Root Cause:**
- Config reads PORT env var correctly BUT `if __name__ == "__main__"` block exists
- When Railway runs `python -m uvicorn main:app --host 0.0.0.0 --port $PORT`, the CLI flag takes precedence
- CLI flag works fine, but code structure suggests port comes from config only

**Solution:**
- Verified config.py reads PORT env var with fallback
- Kept CLI flag pattern for clarity: `--host 0.0.0.0 --port $PORT`
- Added logging to show actual binding: `logger.info(f"Server host: {settings.SERVER_HOST}:{settings.SERVER_PORT}")`

**Prevention:**
- RULE: Always read PORT from environment with fallback: `int(os.getenv("PORT", 8000))`
- RULE: Always use `0.0.0.0` for host, never `localhost` or `127.0.0.1`
- RULE: Test locally with: `PORT=9999 python -m uvicorn main:app --host 0.0.0.0 --port $PORT`

**Files Changed:**
- `backend/config.py` - verified PORT reading logic
- `backend/main.py` - added startup logging

---

## 5. Deployment Configuration Issues

### Issue: Missing Health Check Validation
**Severity:** MEDIUM - Hard to debug deployment failures
**Error:** `/health` returns 200 even when backend is broken

**Root Cause:**
- Health check only checked if endpoint existed, not if backend was ready
- Railway may see "OK" status but backend isn't actually functional
- Difficult to distinguish between startup issues and runtime issues

**Solution:**
- Enhanced health check to validate Supabase connection
- Returns 503 (Service Unavailable) if not ready
- Includes connection details in response

**Prevention:**
- RULE: Health checks must validate ALL critical resources
- RULE: Return 503 when starting up, not 200
- RULE: Include useful diagnostics in health response

**Files Changed:**
- `backend/main.py` - enhanced health check with validation

---

### Issue: Insufficient Startup Logging
**Severity:** MEDIUM - Hard to debug on Railway
**Error:** Railway logs show minimal startup information

**Root Cause:**
- Basic logging format didn't include timestamps or module names
- Difficult to correlate startup sequence with errors
- Hard to see exact failure point

**Solution:**
- Enhanced logging with timestamps and module names
- Added startup markers: "Backend module loading", "Backend ready to accept requests"
- Added explicit error logging in all startup paths

**Prevention:**
- RULE: Always include timestamp and module name in log format
- RULE: Log at critical startup points: module load, init start, init success, init failure
- RULE: Use `exc_info=True` in error logs to get full stack traces

**Files Changed:**
- `backend/main.py` - enhanced logging configuration and messages

---

## 6. Frontend Configuration Issues

### Issue: No Runtime Configuration Mechanism
**Severity:** HIGH - Can't adapt to different deployments
**Error:** Frontend hardcoded to single backend URL

**Root Cause:**
- Frontend had no way to discover backend URL at runtime
- Vite build-time env vars don't work for dynamic deployments
- Had to manually change code for each deployment

**Solution:**
- Implemented runtime configuration via Supabase edge function
- Frontend fetches config at app startup
- Backend URL can be changed via Supabase secret without redeploying frontend

**Prevention:**
- RULE: Configuration that changes per deployment must be runtime-injected
- RULE: Use edge functions or config APIs for dynamic configuration
- RULE: Never hardcode deployment-specific values in frontend

**Files Changed:**
- `src/App.tsx` - runtime config loading
- `supabase/functions/get-config/index.ts` - new config service

---

## 7. Security Considerations

### Issue: Credentials in Request Body
**Severity:** MEDIUM - May leak credentials if HTTPS fails
**Context:** `/api/start-audit` accepts username/password in JSON body

**Mitigation:**
- Always use HTTPS (Railway enforces this)
- Future: Consider using secure token exchange instead of password transmission
- Consider storing credentials in Supabase auth instead of session-by-session

**Prevention:**
- RULE: Use HTTPS for all credential transmission
- RULE: Never log password values
- RULE: Prefer token-based auth over password transmission

**Files to Review:**
- `backend/main.py` - `/api/start-audit` endpoint

---

## 8. Documentation & Communication

### Issue: No Deployment Troubleshooting Guide
**Severity:** MEDIUM - Hard to debug deployment issues
**Error:** Various 502 errors with no clear resolution path

**Solution:**
- Created `RAILWAY_502_TROUBLESHOOTING.md` with complete troubleshooting guide
- Created `DEPLOYMENT_CHECKLIST.md` with step-by-step deployment instructions
- Documented all common errors and their solutions

**Prevention:**
- RULE: Create troubleshooting guides during development
- RULE: Document all error messages and their solutions
- RULE: Keep deployment guides up-to-date

**Files Created:**
- `RAILWAY_502_TROUBLESHOOTING.md`
- `DEPLOYMENT_CHECKLIST.md`
- `PYTHON_311_COMPATIBILITY.md`
- `LESSONS_LEARNED.md` (this file)

---

## 9. Type System & Validation Issues

### Issue: No Request Body Validation
**Severity:** LOW - Silently accepts invalid requests
**Error:** Frontend sends JSON, endpoint ignores it

**Solution:**
- Added Pydantic model with type hints
- Automatic validation and error responses
- Generates OpenAPI documentation automatically

**Prevention:**
- RULE: Always use Pydantic models for request/response validation
- RULE: Run `mypy` for static type checking
- RULE: Enable Swagger UI to verify API contracts

**Files Changed:**
- `backend/main.py` - added StartAuditRequest model

---

## 10. Testing & Validation

### Issue: No Pre-Deployment Validation
**Severity:** MEDIUM - Errors discovered during production deploy
**Error:** Issues only caught after pushing to Railway

**Solution:**
- Added Python syntax validation: `python -m py_compile`
- Added frontend build validation: `npm run build`
- Added dependency compatibility checks
- Added module import checks

**Prevention:**
- RULE: Run validation before every commit
- RULE: Check imports with: `python -c "from main import app"`
- RULE: Run frontend build: `npm run build`
- RULE: Verify all dependencies with `pip list`

**Files Changed:**
- Added validation scripts in CI checks

---

## Summary Table: All Issues & Resolutions

| # | Issue | Severity | Root Cause | Fix | Prevention |
|---|-------|----------|-----------|-----|-----------|
| 1 | gotrue 2.9.1 + httpx conflict | CRITICAL | Version mismatch | Pin versions | Test deps locally |
| 2 | Hardcoded CORS | HIGH | Whitelist logic | Dynamic CORS | Use env vars |
| 3 | VITE_AUDIT_API_URL not injected | HIGH | Build-time only | Edge function | Runtime config |
| 4 | POST body vs query mismatch | MEDIUM | Contract issue | Pydantic model | Define contracts first |
| 5 | Module-level init crash | CRITICAL | Import failure | Move to lifespan | Test imports |
| 6 | Port binding unclear | HIGH | Config structure | Enhanced logging | Always use PORT env |
| 7 | No health validation | MEDIUM | Incomplete check | Validate deps | Check all resources |
| 8 | Insufficient logging | MEDIUM | Basic format | Enhanced format | Log every startup step |
| 9 | No runtime config | HIGH | Build-time only | Edge function | Runtime injection |
| 10 | No validation | MEDIUM | Manual testing | Scripts + build checks | Automate checks |

---

## Action Items for Future Development

### Before Every Deploy:
- [ ] Run `python -m py_compile backend/*.py`
- [ ] Run `npm run build` (ensure no errors)
- [ ] Verify all env vars set in Railway: SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY
- [ ] Check Railway deployment logs (not just status)
- [ ] Test `/health` endpoint returns 200 with "supabase": "connected"
- [ ] Run one end-to-end audit to verify workflow

### Before Every Code Change:
- [ ] Check `LESSONS_LEARNED.md` for related issues
- [ ] Test changes don't crash module imports
- [ ] Update CORS/config if adding new domains
- [ ] Document any new environment variables

### Regular Maintenance:
- [ ] Review Railway logs weekly for errors
- [ ] Update `LESSONS_LEARNED.md` when new issues found
- [ ] Refactor module-level code to use lifespan pattern
- [ ] Monitor dependency updates for security patches

---

## Quick Checklist for Future 502 Errors

If you see a 502 on Railway:

1. Check Railway deployment logs (full logs, not status)
2. Look for "TypeError", "ValueError", "ImportError" - module crash?
3. Look for missing environment variables - secrets not set?
4. Look for "Uvicorn running on" - if not present, app never started
5. Check host binding: should show `0.0.0.0`, not `localhost`
6. Check port: should be dynamic (like 8080), read from $PORT
7. Test locally: `PORT=9999 python -m uvicorn main:app --host 0.0.0.0 --port $PORT`
8. Check `/health` endpoint: `curl https://your-url/health`
9. Review last 3 successful deploys for differences

---

## Related Documentation

- `RAILWAY_502_TROUBLESHOOTING.md` - Detailed 502 debugging guide
- `DEPLOYMENT_CHECKLIST.md` - Step-by-step deployment verification
- `PYTHON_311_COMPATIBILITY.md` - Python version & dependency compatibility
