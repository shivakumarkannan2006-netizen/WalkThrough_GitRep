# Shield Agent - Complete Deployment Guide

## Overview
This guide ensures the backend (Railway) and frontend (Bolt.new) connect properly with all secrets configured correctly.

---

## Part 1: Railway Backend Deployment

### Step 1: Connect Backend Repository to Railway
1. Go to [Railway Dashboard](https://railway.app)
2. Create a new project or select existing "walkthroughgitrep"
3. Connect to the GitHub repository
4. Select the `backend/` folder as the root directory (or ensure railway.json is detected)
5. Click "Deploy"

### Step 2: Configure Railway Variables (CRITICAL)
Railway **must** inject these environment variables. Go to your Railway service → Variables tab:

| Variable Name | Value | Purpose |
|---|---|---|
| `PORT` | `8080` | App port (matches Dockerfile EXPOSE) |
| `SUPABASE_URL` | `https://rhjyhompsdbvyixtwphw.supabase.co` | Supabase project URL |
| `SUPABASE_KEY` | *(Your anon key from Supabase dashboard)* | Supabase anonymous key |
| `SUPABASE_SERVICE_ROLE_KEY` | *(Your service role key)* | Supabase service role for RLS bypass |
| `GEMINI_API_KEY` | *(Your Google Gemini API key)* | For AI analysis features |
| `BROWSERBASE_API_KEY` | *(Optional)* | For stealth browsing (if using) |
| `BROWSERBASE_PROJECT_ID` | *(Optional)* | For stealth browsing (if using) |

**How to add variables:**
1. Open Railway service → Settings → Variables tab
2. Click "+ Add Variable" for each entry
3. Paste the exact name and value
4. Click Save

**How to get Supabase keys:**
1. Log into [Supabase Dashboard](https://app.supabase.com)
2. Select your project `rhjyhompsdbvyixtwphw`
3. Go to Settings → API
4. Copy:
   - `Project URL` → use as `SUPABASE_URL`
   - `anon public` → use as `SUPABASE_KEY`
   - `service_role secret` → use as `SUPABASE_SERVICE_ROLE_KEY`

### Step 3: Verify Railway Networking
1. Go to Railway service → Settings → Networking
2. **Verify Target Port is `8080`**
   - If showing a different port, click edit and set to `8080`
3. Copy the **Public Domain URL** (looks like `https://walkthroughgitrep-production.up.railway.app`)

### Step 4: Deploy and Verify Backend
1. In Railway, watch the Deployment logs
2. Look for: `INFO: Application startup complete`
3. Test health endpoint:
   ```bash
   curl https://walkthroughgitrep-production.up.railway.app/health
   ```
4. **Expected response:**
   ```json
   {
     "status": "ok",
     "service": "Shield Agent API",
     "supabase": "connected",
     "port": 8080
   }
   ```

If you see `"supabase": "unavailable"`, your env vars aren't set. Go back to Step 2.

---

## Part 2: Bolt.new Frontend Deployment

### Step 1: Set Frontend Environment Variable
1. Open your Bolt.new project
2. In the terminal at bottom, stop any running dev server (Ctrl+C)
3. Go to project settings/environment
4. Add this exact variable:
   - **Key:** `VITE_AUDIT_API_URL`
   - **Value:** `https://walkthroughgitrep-production.up.railway.app` (your Railway domain from Step 3 above)

### Step 2: Rebuild Frontend
1. In terminal, run:
   ```bash
   npm run build
   ```
2. Wait for build to complete (should say "built in X.XXs")

### Step 3: Deploy to Bolt.new
1. Commit and push changes, or use Bolt's native deploy feature
2. Your frontend will automatically rebuild with the new `VITE_AUDIT_API_URL`

### Step 4: Verify Connection
1. Open your Bolt.new deployed site
2. Open DevTools: Press F12 → Console tab
3. Look for logs starting with `[SHIELD]`:
   - `[SHIELD] AUDIT_API from build-time env: https://walkthroughgitrep-production.up.railway.app` ✓
   - `[SHIELD] Backend response status: 200` ✓
   - `[SHIELD] WebSocket connected` ✓

If you see `[SHIELD] AUDIT_API not configured`, the env var wasn't set correctly. Return to Part 2, Step 1.

---

## Part 3: Troubleshooting

### Issue: "Backend not connected" Error in Frontend
**Cause:** `VITE_AUDIT_API_URL` is empty or wrong.
**Fix:**
1. Verify the env var is set in Bolt.new to `https://walkthroughgitrep-production.up.railway.app`
2. Run `npm run build` again
3. Redeploy

### Issue: 502 Bad Gateway on Railway
**Cause:** App not listening on correct port or secrets missing.
**Fix:**
1. Check Railway logs: look for `ERROR: Failed to initialize Supabase`
2. Go to Variables tab and add missing env vars (especially `SUPABASE_URL`, `SUPABASE_KEY`)
3. Redeploy

### Issue: Health Check Returns 503
**Cause:** Supabase client failed to initialize.
**Fix:**
1. Check Railway Variables are correct (copy/paste from Supabase exactly)
2. Ensure `SUPABASE_URL` ends with `.supabase.co`
3. Ensure `SUPABASE_KEY` is the **anon key**, not service role
4. Redeploy after fixing

### Issue: WebSocket Connection Fails
**Cause:** Frontend can't establish persistent connection to backend.
**Fix:**
1. Check that backend health check passes: `curl https://your-railway-url/health`
2. Check DevTools → Network → WS tab to see WebSocket handshake
3. If 403, check CORS settings in `backend/config.py` (should allow your Bolt.new domain)

### Issue: Playwright Chromium Installation Fails
**Cause:** Docker build error on Railway.
**Fix:**
1. Check build logs for `apt-get` errors
2. Dockerfile has all necessary system dependencies
3. If still failing, try triggering a rebuild in Railway settings

---

## Part 4: File Checklist

Verify these files exist and are correct:

- ✓ `/backend/railway.json` — Configures `$PORT` expansion with `sh -c`
- ✓ `/backend/Dockerfile` — No secrets in ARG/ENV, correct EXPOSE 8080
- ✓ `/backend/requirements.txt` — All dependencies pinned
- ✓ `/backend/runtime.txt` — Python 3.11.9
- ✓ `/backend/config.py` — Reads PORT env var correctly
- ✓ `/backend/main.py` — All endpoints check `if supabase:` before use
- ✓ `/.env` — Contains `VITE_AUDIT_API_URL` for local dev
- ✓ `/vite.config.ts` — Configured for Vite build

---

## Part 5: Manual Testing Commands

Test backend from command line:

```bash
# Health check
curl https://walkthroughgitrep-production.up.railway.app/health

# Start audit (example)
curl -X POST https://walkthroughgitrep-production.up.railway.app/api/start-audit \
  -H "Content-Type: application/json" \
  -d '{"target_url": "https://example.com", "company_id": "test-123"}'

# Get status (replace SESSION_ID with actual)
curl https://walkthroughgitrep-production.up.railway.app/api/audit/SESSION_ID/status
```

Test frontend build:

```bash
# Build frontend locally
npm run build

# Check dist/ folder exists and has index.html
ls -lah dist/
```

---

## Summary: Complete Fix Checklist

- [ ] Railway Variables added (PORT, SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY, GEMINI_API_KEY)
- [ ] Railway Target Port set to 8080
- [ ] Backend health check returns 200 with "supabase": "connected"
- [ ] Frontend VITE_AUDIT_API_URL env var set to Railway URL
- [ ] Frontend rebuilt and deployed
- [ ] DevTools console shows [SHIELD] logs without errors
- [ ] "Start Audit" button works and connects to backend

Once all items are checked, your deployment is complete!
