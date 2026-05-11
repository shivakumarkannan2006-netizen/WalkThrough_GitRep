# Railway 502 Bad Gateway - Complete Troubleshooting Guide

## What is a 502 Bad Gateway?

A 502 error on Railway means:
- Railway's proxy (load balancer) IS online and reachable
- Your application's process is NOT listening on the correct port
- Or your application crashed during startup

**Railway will only mark your deploy as "success" if the app successfully binds to the port and serves traffic.**

---

## Root Causes & Solutions (Ordered by Likelihood)

### 1. **Port Binding Issue (MOST COMMON)**

**Problem:** App is hardcoded to listen on port 3000 or 8000, but Railway injects a dynamic port.

**Symptoms:**
- 502 Bad Gateway on every request
- Railway logs show app is "running" but no traffic reaches it
- Curl to your Railway URL returns 502

**Fix - Python/Uvicorn:**
```python
# WRONG - hardcoded port, Railway can't inject PORT env var
import uvicorn
uvicorn.run(app, host="localhost", port=8000)

# CORRECT - read PORT from environment, default to 8000 for local dev
import os
port = int(os.getenv("PORT", 8000))
uvicorn.run(app, host="0.0.0.0", port=port)
```

**Key Details:**
- Must bind to `0.0.0.0`, NOT `localhost` or `127.0.0.1`
- `0.0.0.0` means "listen on ALL network interfaces"
- `localhost` only works for connections from the same machine
- Railway's proxy connects via internal network, not localhost

**How It's Passed:**
- Railway sets the `PORT` environment variable (e.g., `PORT=8080`)
- Start command must use it: `python -m uvicorn main:app --host 0.0.0.0 --port $PORT`
- Config reads it: `port = int(os.getenv("PORT", os.getenv("SERVER_PORT", "8000")))`

---

### 2. **Module Import Crash (CRASHES BEFORE BINDING)**

**Problem:** Python code at module level crashes on import, before FastAPI app even starts.

**Symptoms:**
- Railway log shows build succeeded
- But startup logs end abruptly with no "app listening" message
- 502 on all requests immediately after deploy

**Example from this project (FIXED):**
```python
# WRONG - crashes at import time if env vars missing
supabase = init_supabase()  # At module level

# Result: If SUPABASE_URL or SUPABASE_KEY not set, entire app fails to import
# Uvicorn can't even load main:app, returns 502
```

**Fix:**
```python
# CORRECT - initialize during app startup
supabase = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global supabase
    try:
        supabase = init_supabase()  # Initialize during startup, not import
        logger.info("Backend ready")
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    yield
    # cleanup...

app = FastAPI(lifespan=lifespan)
```

**Why This Matters:**
- When uvicorn runs `python -m uvicorn main:app`, it imports `main.py`
- If ANY code at module level crashes, the app import fails
- Uvicorn has no app to run → 502
- Moving initialization to `lifespan()` delays it until after app is loaded

---

### 3. **Missing Environment Variables**

**Problem:** Your code reads an env var that Railway hasn't set.

**Symptoms:**
- Railway deploy "succeeds" (green checkmark)
- But app won't start or 502 immediately
- Railway logs show `ValueError: SUPABASE_URL and SUPABASE_KEY must be set`

**Fix:**
1. Go to Railway project dashboard
2. Click on your service (e.g., "backend")
3. Go to "Variables" tab
4. Add all required secrets:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `GEMINI_API_KEY`
   - Any others your app needs

5. Redeploy after adding variables

**Best Practice:**
- Never crash on missing optional vars
- Log warnings instead of raising errors for optional config
- Fail gracefully with meaningful error messages

Example:
```python
# BAD - crashes if env var missing
api_key = os.getenv("GEMINI_API_KEY")  # Will be None if not set, crashes later
result = client.call(api_key=api_key)  # TypeError: NoneType not valid

# GOOD - explicit check with helpful message
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    logger.warning("GEMINI_API_KEY not set - AI features disabled")
    # Handle gracefully or raise early with context
    raise ValueError("GEMINI_API_KEY environment variable required for this operation")
```

---

### 4. **Dependency Installation Failed**

**Problem:** `pip install -r requirements.txt` fails during Railway build.

**Symptoms:**
- Build logs show `ERROR: ... Failed building wheel for ...`
- Deploy "failed" status in Railway
- No 502 error (because app never starts)

**Fix:**
- Check Railway build logs for the actual error
- Common issues:
  - Incompatible package versions (e.g., gotrue 2.9.1 + httpx 0.25.2)
  - Missing system dependencies (e.g., PostgreSQL dev headers)
  - Python version mismatch (require Python 3.11.9 but pkg expects 3.10)

**For this project (ALREADY FIXED):**
- All versions pinned for Python 3.11.9 in `requirements.txt`
- gotrue 2.8.1 explicitly pinned (compatible with httpx 0.25.2)

---

### 5. **Process Exits Immediately After Startup**

**Problem:** App starts, binds to port, but then crashes or exits.

**Symptoms:**
- 502 after ~5 seconds instead of immediately
- Railway eventually marks as "failed"
- No error in logs (or cryptic error)

**Causes:**
- Unhandled exception in startup code
- Resource exhaustion (out of memory)
- Critical dependency failure

**Fix:**
- Wrap startup in try/catch with detailed logging
- Check Railway resource limits (CPU/memory)
- Review crash logs for stack traces

Example:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Initializing resources...")
        supabase = init_supabase()
        logger.info("✓ Supabase connected")
        # More initializations...
        logger.info("✓ All systems ready")
    except Exception as e:
        logger.error(f"✗ Startup failed: {e}", exc_info=True)  # exc_info=True shows full traceback
        raise
    yield
    logger.info("Shutting down...")
```

---

## Debugging Checklist for 502 Errors

When you see 502 on Railway, run through this checklist:

- [ ] Check Railway deploy logs (not just status)
  - Click "Deployments" tab, find the failed/current deploy
  - Click on it to see full logs
  - Look for errors in the "Build" and "Logs" sections

- [ ] Verify PORT is in `config.py`:
  ```python
  SERVER_PORT: int = int(os.getenv("PORT", os.getenv("SERVER_PORT", "8000")))
  ```

- [ ] Verify host is `0.0.0.0`:
  ```python
  SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
  uvicorn.run(app, host=settings.SERVER_HOST, port=settings.SERVER_PORT)
  ```

- [ ] Verify start command is correct:
  - Should be: `python -m uvicorn main:app --host 0.0.0.0 --port $PORT`
  - NOT: `python main.py` (bypasses CLI flags)

- [ ] Verify all required secrets are set in Railway:
  - Go to service → Variables
  - Check: `SUPABASE_URL`, `SUPABASE_KEY`, `GEMINI_API_KEY`, etc.

- [ ] Verify no module-level code crashes on import:
  - Move expensive initialization to `lifespan()` or lazy-loaded functions
  - Test locally: `python -c "from main import app"` should work

- [ ] Check Python version matches:
  - Project uses Python 3.11.9 (set in `runtime.txt`)
  - Verify all packages support 3.11.9

- [ ] Check build log for dependency errors:
  - `pip install -r requirements.txt` should succeed
  - No incompatible package versions

- [ ] Add `/health` endpoint and curl it:
  ```bash
  curl https://your-railway-url/health
  ```
  - Should return 200 with JSON
  - If 502, the app didn't start

---

## Fixes Applied to This Project

### Issue: Module-Level Supabase Initialization
**Before (BROKEN):**
```python
# At module level - crashes if env vars missing
supabase = init_supabase()  # Runs during import
```

**After (FIXED):**
```python
# Global initialized to None
supabase = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global supabase
    try:
        supabase = init_supabase()  # Runs during startup
        logger.info("Backend ready to accept requests")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase: {e}")
        raise  # Fails gracefully with meaningful error
    yield
    logger.info("Shutting down...")
```

### Issue: No Startup Validation
**Before (RISKY):**
```python
@app.get("/health")
async def health_check():
    return {"status": "ok"}  # Always returns ok, even if backend broken
```

**After (FIXED):**
```python
@app.get("/health")
async def health_check():
    if not supabase:
        raise HTTPException(status_code=503, detail="Backend starting up")
    return {
        "status": "ok",
        "service": "Shield Agent API",
        "supabase": "connected",
    }
```

### Issue: No Logging at Startup
**Before (HARD TO DEBUG):**
```python
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

**After (EASY TO DEBUG):**
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Backend module loading...")
```

---

## Prevention Rules (For Future Development)

**Never do this:**
1. Initialize expensive resources at module level (do it in `lifespan()`)
2. Hardcode ports (always use `os.getenv("PORT", default)`)
3. Bind to `localhost` (always use `0.0.0.0`)
4. Use query params when frontend sends JSON body
5. Miss secrets in Railway (always verify before deploy)

**Always do this:**
1. Move initialization to startup/lifespan
2. Use environment variables with fallbacks
3. Bind to `0.0.0.0` on port from `$PORT` env var
4. Add validation in endpoints to check resource readiness
5. Test health check locally before deploying
6. Check Railway deploy logs (not just status) when debugging

---

## Quick Reference: Correct Backend Startup Pattern

```python
import os
import logging
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

# 1. Setup logging early
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Application starting...")

# 2. Read config with proper defaults
PORT = int(os.getenv("PORT", 8000))
HOST = os.getenv("HOST", "0.0.0.0")

# 3. Initialize global state to None
supabase = None
cache = None

# 4. Use lifespan for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    global supabase, cache
    
    logger.info(f"Binding to {HOST}:{PORT}")
    try:
        supabase = init_supabase()
        cache = init_cache()
        logger.info("✓ All systems ready")
    except Exception as e:
        logger.error(f"✗ Startup failed: {e}", exc_info=True)
        raise
    
    yield
    
    logger.info("Shutting down...")
    if supabase:
        supabase.close()

app = FastAPI(lifespan=lifespan)

# 5. Validate in endpoints
@app.get("/health")
async def health():
    if not supabase:
        raise HTTPException(status_code=503, detail="Starting up")
    return {"status": "ok"}

# 6. If needed, run with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
```

**Railway start command:**
```bash
python -m uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

## Success Indicators

When fixed, Railway logs should show:
```
Application starting...
Binding to 0.0.0.0:8080
✓ All systems ready
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
```

And your health check should return:
```bash
$ curl https://your-railway-url/health
{"status":"ok","service":"Shield Agent API","supabase":"connected","port":8080}
```
