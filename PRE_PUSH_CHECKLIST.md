# Pre-Push Checklist - Before Committing to GitHub

Run through this checklist before pushing to GitHub. Each item must pass before proceeding.

---

## Code Validation

- [ ] **Python Syntax Check**
  ```bash
  python3 -m py_compile backend/main.py backend/db.py backend/config.py
  ```
  Expected: No output = Success

- [ ] **Frontend Build Check**
  ```bash
  npm run build
  ```
  Expected: `✓ built in X.XXs`

- [ ] **Module Import Check (Optional)**
  ```bash
  cd backend && python3 -c "from config import get_settings; print('OK')"
  ```
  Expected: `OK` (if dependencies installed) or `ModuleNotFoundError: dotenv` (expected in CI)

---

## Code Content Verification

- [ ] **No Module-Level Supabase Init**
  ```bash
  grep "^supabase = init_supabase()" backend/main.py
  ```
  Expected: No output (should NOT find this line)

- [ ] **Supabase Init in Lifespan**
  ```bash
  grep -A2 "async def lifespan" backend/main.py | grep "supabase = init_supabase()"
  ```
  Expected: Should find the line (init in lifespan)

- [ ] **Health Check Validates Supabase**
  ```bash
  grep -A3 "@app.get(\"/health\")" backend/main.py | grep "if not supabase"
  ```
  Expected: Should find the validation check

- [ ] **PORT Environment Variable Used**
  ```bash
  grep 'os.getenv("PORT"' backend/config.py
  ```
  Expected: Should find PORT configuration

- [ ] **CORS Supports Wildcards**
  ```bash
  grep "bolt" backend/config.py
  ```
  Expected: Should find wildcard patterns for bolt.new and railway.app

- [ ] **Request Model Present**
  ```bash
  grep "class StartAuditRequest" backend/main.py
  ```
  Expected: Should find Pydantic model

- [ ] **Dependencies Pinned**
  ```bash
  grep -E "supabase==|gotrue==|httpx==" backend/requirements.txt
  ```
  Expected: Should show:
  - supabase==2.3.4
  - gotrue==2.8.1
  - httpx==0.25.2

- [ ] **Python Version Locked**
  ```bash
  cat backend/runtime.txt
  ```
  Expected: `python-3.11.9`

---

## Documentation Check

- [ ] **Lessons Learned Document Exists**
  ```bash
  ls -la LESSONS_LEARNED.md
  ```
  Expected: File exists and is readable

- [ ] **Railway Troubleshooting Guide Exists**
  ```bash
  ls -la RAILWAY_502_TROUBLESHOOTING.md
  ```
  Expected: File exists and is readable

- [ ] **Deployment Checklist Exists**
  ```bash
  ls -la DEPLOYMENT_CHECKLIST.md
  ```
  Expected: File exists and is readable

- [ ] **Final Summary Exists**
  ```bash
  ls -la FINAL_DEPLOYMENT_SUMMARY.md
  ```
  Expected: File exists and is readable

---

## Git Status Check

- [ ] **Review All Changes**
  ```bash
  git status
  ```
  Expected: See all modified files listed

- [ ] **Review Changed Backend Files**
  ```bash
  git diff backend/main.py | head -50
  git diff backend/config.py | head -50
  git diff backend/db.py | head -50
  git diff backend/requirements.txt
  ```
  Expected: Changes should match fixes described in FINAL_DEPLOYMENT_SUMMARY.md

- [ ] **Review Changed Frontend Files**
  ```bash
  git diff src/App.tsx | head -50
  ```
  Expected: Should show edge function integration

---

## Final Verification

- [ ] **All Critical Fixes Present**
  - [ ] Module-level init removed ✓
  - [ ] Lifespan initialization added ✓
  - [ ] Health check validation added ✓
  - [ ] CORS middleware added ✓
  - [ ] Edge function deployed ✓
  - [ ] Dependencies pinned ✓
  - [ ] Logging enhanced ✓

- [ ] **No Regressions**
  - [ ] Frontend still builds
  - [ ] No new syntax errors
  - [ ] No deprecated patterns

- [ ] **Documentation Complete**
  - [ ] All issues documented ✓
  - [ ] All fixes documented ✓
  - [ ] Troubleshooting guide complete ✓
  - [ ] Deployment steps clear ✓

---

## Commit Message

Use this commit message:

```
Fix all Railway 502 Bad Gateway issues and Python compatibility

Summary of changes:
- Fixed module-level Supabase initialization (was crashing at import)
- Moved initialization to lifespan() with proper error handling
- Enhanced health check to validate Supabase connection
- Fixed CORS to support *.bolt.new and *.up.railway.app domains
- Added custom CORS middleware for wildcard pattern support
- Fixed POST body parsing for /api/start-audit endpoint
- Added StartAuditRequest Pydantic model for validation
- Fixed Python 3.11.9 dependency conflicts:
  - Downgraded supabase 2.4.0 → 2.3.4
  - Pinned gotrue 2.8.1 (compatible with httpx 0.25.2)
- Enhanced startup logging with timestamps and detailed messages
- Added runtime configuration injection for backend URL discovery
- Deployed get-config edge function for VITE_AUDIT_API_URL
- Updated documentation with deployment guides and troubleshooting

Issues fixed:
1. Railway 502 Bad Gateway (module-level init crash)
2. gotrue 2.9.1 + httpx 0.25.2 incompatibility
3. CORS blocking frontend requests
4. VITE_AUDIT_API_URL not available at runtime
5. POST body vs query parameter mismatch
6. Incomplete health check validation
7. Insufficient startup logging

All checks passed. Ready for production deployment.
```

---

## Final Steps Before Push

1. **Run All Checks Above** - Ensure every item has ✓

2. **Commit Changes**
   ```bash
   git add -A
   git commit -m "Fix all Railway 502 Bad Gateway issues and Python compatibility

   [Full message from above]
   "
   ```

3. **Review Commit**
   ```bash
   git log -1 --stat
   ```
   Expected: See all changed files and line counts

4. **Push to GitHub**
   ```bash
   git push origin main
   ```
   Expected: No errors, shows branches updated

5. **Monitor Railway Deployment**
   - Go to Railway dashboard
   - Click on your backend service
   - Watch deployment progress in "Deployments" tab
   - Wait for "Deploy Successful" status
   - Check deploy logs for "Backend ready to accept requests"

6. **Verify After Deploy**
   - Test health endpoint: `curl https://your-railway-url/health`
   - Check Bolt frontend console for `[SHIELD] AUDIT_API loaded...`
   - Run a test audit
   - Monitor Railway logs for errors

---

## If Push Fails

Check these before retrying:

- [ ] Git status clean (no uncommitted changes)
- [ ] Remote branch exists (git fetch to update)
- [ ] Authentication set up (GitHub SSH key or token)
- [ ] Commit message valid (no special characters breaking it)

---

## Success Confirmation

After push and Railway deployment, you should see:

- Railway: "Deploy Successful" status
- Railway logs: "Backend ready to accept requests"
- Health check: Returns 200 with supabase connected
- Frontend: Console shows backend URL loaded
- Audit: First test succeeds without errors

---

**DO NOT SKIP ANY CHECKS**

This checklist prevents deploying broken code to production.
