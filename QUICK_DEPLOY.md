# Quick Deploy Checklist - 5 Minutes

## Before You Start
- Have your Supabase dashboard open: https://app.supabase.com
- Have your Railway dashboard open: https://railway.app
- Have your Bolt.new project open

---

## Step 1: Railway Variables (2 minutes)
Go to Railway → Your Service → Settings → Variables

**Copy/paste these EXACTLY:**

```
PORT = 8080

SUPABASE_URL = https://rhjyhompsdbvyixtwphw.supabase.co

SUPABASE_KEY = [anon key from Supabase dashboard]

SUPABASE_SERVICE_ROLE_KEY = [service_role secret from Supabase dashboard]

GEMINI_API_KEY = [your Google Gemini API key]
```

**How to get Supabase keys:**
1. Log into Supabase
2. Select project `rhjyhompsdbvyixtwphw`
3. Go to Settings → API
4. Copy the three values above

**Save and Trigger Redeploy**

---

## Step 2: Check Railway Networking (1 minute)
1. Railway → Service → Settings → Networking
2. Verify **Target Port = 8080**
3. Copy the **Public Domain URL** (looks like `https://walkthroughgitrep-production.up.railway.app`)

---

## Step 3: Verify Backend Works (1 minute)
Open a terminal and run:
```bash
curl https://walkthroughgitrep-production.up.railway.app/health
```

**Expected:** Should see `"supabase": "connected"`

If you see `"unavailable"`, your env vars aren't right. Go back to Step 1.

---

## Step 4: Bolt.new Frontend (1 minute)
1. Go to your Bolt.new project
2. Settings → Environment Variables
3. Add:
   - **Key:** `VITE_AUDIT_API_URL`
   - **Value:** `https://walkthroughgitrep-production.up.railway.app` (your Railway domain from Step 2)
4. Save

---

## Step 5: Rebuild & Deploy (1 minute)
In Bolt.new terminal:
```bash
npm run build
```

Then commit/push or use Bolt's deploy button.

---

## Test It
1. Open your Bolt.new site
2. Press F12 → Console
3. Look for `[SHIELD]` logs
4. Click "Start Audit"
5. **It should work now!**

---

## If It Doesn't Work

### See `[SHIELD] AUDIT_API not configured`
→ Frontend env var not set. Go back to Step 4.

### See `[SHIELD] Backend error response: 503`
→ Supabase not ready. Check Railway logs for `ERROR: Failed to initialize Supabase`. Go back to Step 1.

### See `[SHIELD] WebSocket error`
→ Network issue. Check that Railway health check passes (Step 3).

### See `502 Bad Gateway`
→ Railway app crashed. Check Railway logs. Check that PORT=8080 in variables (Step 1).

---

## That's It!
Your backend and frontend are now connected. Enjoy!
