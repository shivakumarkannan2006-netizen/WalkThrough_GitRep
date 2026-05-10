# Shield Agent - Quick Start Guide (5 minutes)

## Prerequisites Check
- ✅ Node.js installed: `node -v` (should be 18+)
- ✅ Python installed: `python --version` (should be 3.9+)
- ✅ Supabase project created (database already provisioned)
- ✅ OpenAI API key or Gemini API key

## Step 1: Backend Setup (2 minutes)

```bash
# Navigate to backend
cd backend

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install

# Set up environment
cp .env.example .env
# Edit .env with your:
# - SUPABASE_URL
# - SUPABASE_KEY
# - SUPABASE_SERVICE_ROLE_KEY
# - OPENAI_API_KEY (or GEMINI_API_KEY)

# Start backend
python main.py
```

**✅ Backend running at `http://localhost:8000`**

Check health: `curl http://localhost:8000/health`

## Step 2: Frontend Setup (2 minutes)

Open a **new terminal** and run:

```bash
# From project root
npm install
npm run dev
```

**✅ Frontend running at `http://localhost:5173`**

## Step 3: Run Your First Audit (1 minute)

1. Open `http://localhost:5173` in browser
2. Enter a URL (try `https://example.com`)
3. (Optional) Add login credentials
4. Click "Start Audit"
5. Watch real-time crew activity and issues appear

## What You'll See

**Crew Activity Feed** (Real-time updates as agents work)
```
👻 Ghost Navigator - Checking form loops
🪞 Mirror Stylist - Analyzing contrast
🔐 Vault Counsel - GDPR compliance check
...
```

**Issues Discovered** (Sorted by severity)
- 🔴 **CRITICAL** - Security leaks, GDPR violations
- 🟠 **HIGH** - Broken features, accessibility failures
- 🟡 **MEDIUM** - UX issues, styling problems
- 🔵 **LOW** - Polish, minor suggestions

**Crew Summary** (Issue count per agent)
- Ghost Navigator: 3 issues
- Mirror Stylist: 7 issues
- Vault Counsel: 1 issue
- (etc.)

## Understanding the Results

### Example Issues by Agent

**Ghost Navigator** (Logic & Reliability)
- ❌ Form accepts spacebar-only input
- ❌ Anchor link points to broken target
- ❌ Page missing back button or home link

**Mirror Stylist** (Aesthetics & UX)
- ⚠️ Low contrast: white text on light gray
- ⚠️ Button too small for mobile (32x32px < 48x48px)
- ⚠️ Horizontal scroll detected on mobile

**Vault Counsel** (Compliance & Legal)
- 🔒 Missing GDPR language on privacy page
- 🔒 Tracking cookie set before consent
- 🔒 Price differs between pages ($99 vs $119)

**Fact Checker** (Verification)
- ✅ All external links reachable
- ⚠️ Testimonial sounds AI-generated (80% confidence)

**Fortress Sentry** (Security & Privacy)
- 🛡️ API key leaked in console logs
- 🛡️ Password field not properly masked
- 🛡️ Image contains GPS location (EXIF)

**Vision Architect** (Psychology & Value)
- 💡 Add lifestyle imagery for luxury appeal
- 💡 Add customer testimonials for social proof
- 💡 Tone inconsistent: casual → formal

## Database Verification

Your Supabase database now has:
- ✅ 27 audit and findings tables
- ✅ Row-level security on all tables
- ✅ Proper indexes for performance
- ✅ Audit session tracking
- ✅ Complete issue history

View in Supabase Dashboard:
- `audit_sessions` - See running/completed audits
- `audit_issues` - View all discovered issues
- `audit_pages` - See pages discovered by BFS
- (and 24 more specialized tables)

## API Endpoints for Testing

```bash
# Start an audit
curl -X POST http://localhost:8000/api/start-audit \
  -H "Content-Type: application/json" \
  -d '{
    "target_url": "https://example.com",
    "company_id": "test-company"
  }'

# Get audit status
curl http://localhost:8000/api/audit/{session-id}/status

# List discovered issues
curl http://localhost:8000/api/audit/{session-id}/issues

# Get complete report
curl http://localhost:8000/api/audit/{session-id}/report

# View API docs
# Open http://localhost:8000/docs in browser
```

## Common Issues

**"Backend won't start"**
```bash
# Check Python version
python --version  # Should be 3.9+

# Check dependencies
pip list | grep -E "fastapi|playwright|supabase"

# Verify Supabase credentials in .env
cat backend/.env | grep SUPABASE
```

**"WebSocket connection failed"**
- Ensure backend is running on localhost:8000
- Check browser console for CORS errors
- Verify firewall isn't blocking ports

**"No pages discovered"**
- Check URL is accessible in browser first
- Verify Playwright installed: `python -c "import playwright; playwright.sync_api.sync_playwright()"`
- Check browser console for JavaScript errors

**"LLM analysis not working"**
- Verify API key in .env
- Check API quota/billing
- Review backend logs for rate limiting

## Monitoring Progress

During an audit, you can:
1. **Watch live feed** - See each agent's actions
2. **Check dashboard** - Real-time issue count
3. **Monitor database** - Query Supabase directly
4. **View logs** - Backend console shows detailed progress

Typical timeline for a 20-page site:
- 0-10s: Landing page analysis
- 10-30s: BFS discovers 5-10 pages
- 30-60s: Crew agents analyze pages in parallel
- 60-120s: External link verification
- Total: 1-2 minutes for complete audit

## Next Steps

### For Testing
- Try auditing: example.com, google.com, github.com
- Test with credentials if site requires login
- Upload legal PDFs to test Vault Counsel (future feature)

### For Production
1. Follow `SETUP.md` for environment configuration
2. Deploy backend to Railway/Docker
3. Deploy frontend to Vercel/GitHub Pages
4. Connect to production Supabase database
5. Configure monitoring and alerting

### For Enhancement
- Add custom alert rules
- Create automated remediation suggestions
- Generate GitHub issues from audit results
- Set up automated daily audits

## Documentation Files

- **SETUP.md** - Complete installation & deployment guide
- **README.md** - Project overview and features
- **IMPLEMENTATION_SUMMARY.md** - Detailed feature verification
- **QUICK_START.md** - This file

## Support

If something doesn't work:

1. **Check logs**
   ```bash
   # Backend logs appear in terminal where you ran: python main.py
   # Frontend logs appear in browser console (F12)
   ```

2. **Verify connectivity**
   ```bash
   # Check backend is responding
   curl http://localhost:8000/health
   
   # Check Supabase connection
   curl -H "Authorization: Bearer YOUR_KEY" \
     https://YOUR_SUPABASE_URL/rest/v1/audit_sessions?limit=1
   ```

3. **Review configuration**
   ```bash
   # Verify all env vars are set
   cd backend && grep -v '^#' .env | grep -v '^$'
   ```

## That's It! 🚀

You now have a production-grade web auditing platform that:
- ✅ Autonomously traverses any website
- ✅ Tests all features and pages
- ✅ Detects 27+ issue categories
- ✅ Runs 6 specialized agents in parallel
- ✅ Provides real-time feedback
- ✅ Stores complete audit history

**Start auditing AI-generated websites with confidence!**
