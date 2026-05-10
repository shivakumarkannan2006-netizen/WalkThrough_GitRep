# Shield Agent - Web Auditing Platform Setup Guide

## Project Structure

```
project/
├── backend/              # FastAPI Python backend
│   ├── main.py          # FastAPI entry point
│   ├── config.py        # Configuration settings
│   ├── db.py            # Supabase initialization
│   ├── navigator.py     # Playwright BFS traversal engine
│   ├── crew.py          # 6 specialized crew agents
│   ├── requirements.txt # Python dependencies
│   └── .env.example     # Environment variables template
│
├── src/                 # React frontend
│   ├── App.tsx         # Main audit dashboard
│   ├── main.tsx        # Entry point
│   └── index.css       # Tailwind styles
│
└── database/            # Supabase schema migrations
```

## Prerequisites

- Node.js 18+
- Python 3.9+
- Git
- Supabase account (database already provisioned)
- OpenAI or Gemini API key (for LLM analysis)

## Backend Setup

### 1. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Install Playwright Browsers

```bash
playwright install
```

### 3. Configure Environment Variables

```bash
# Copy example to .env
cp .env.example .env

# Edit .env with your values:
# - SUPABASE_URL
# - SUPABASE_KEY
# - SUPABASE_SERVICE_ROLE_KEY
# - OPENAI_API_KEY (or GEMINI_API_KEY)
```

### 4. Start FastAPI Server

```bash
cd backend
python main.py
```

The API will be available at `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

## Frontend Setup

### 1. Install Node Dependencies

```bash
npm install
```

### 2. Start Development Server

```bash
npm run dev
```

Frontend will be available at `http://localhost:5173` or `http://localhost:3000`

## How to Use

1. **Start Backend**: Run FastAPI server on `localhost:8000`
2. **Start Frontend**: Run Vite dev server on `localhost:5173`
3. **Open Dashboard**: Visit `http://localhost:5173`
4. **Enter URL**: Type website URL to audit (e.g., `https://example.com`)
5. **Add Credentials** (optional): For authenticated page testing
6. **Click "Start Audit"**: The crew begins traversal
7. **Watch Activity**: Real-time crew activity and issues appear in dashboard

## Core Components

### Backend Architecture

**Navigator (ShieldNavigator)**
- BFS traversal of website
- Dual-path exploration (authenticated + unauthenticated)
- Playwright auto-wait for reliability
- Screenshot capture at multiple viewports
- AXTree snapshot collection

**Crew Agents** (run in parallel on each page)
1. **Ghost Navigator** - Logic & reliability issues
   - Form validation testing
   - Deep link accuracy
   - Orphaned states
   - 404/broken routes
   - Back button behavior

2. **Mirror Stylist** - Aesthetic & UX issues
   - WCAG contrast failures
   - Z-index collisions
   - Touch target sizing
   - Horizontal scroll bugs
   - Font jumps (FOUT)
   - Mobile integrity

3. **Vault Counsel** - Compliance & integrity
   - GDPR compliance
   - Cookie consent
   - Pricing consistency
   - Contact info matching
   - Dark pattern detection

4. **Fact Checker** - Verification
   - External link verification
   - Testimonial authenticity
   - Citation checking

5. **Fortress Sentry** - Privacy & security
   - Console log leaks
   - Sensitive data masking
   - Image EXIF metadata

6. **Vision Architect** - Psychology & value
   - Empty state analysis
   - Reading level audit
   - Tone consistency
   - Enhancement recommendations

**Internal Monitors**
- DOM mutation tracking
- Performance baseline monitoring
- User persona simulation (frustrated/confused)

### Database Schema

All tables created in Supabase with:
- Row-level security (RLS) policies
- Company and user isolation
- Comprehensive indexing
- Optimized for audit queries

Key tables:
- `audit_sessions` - Audit run tracking
- `audit_pages` - Discovered URLs
- `audit_issues` - All detected issues
- `company_documents` - Legal/policy PDFs for RAG
- `audit_external_links` - Link verification data
- `*_findings` - Agent-specific detailed findings

### Frontend Features

- Real-time crew activity feed via WebSocket
- Live issue detection and display
- Severity filtering (critical → low)
- Agent-based issue grouping
- Page discovery visualization
- Status tracking

## API Endpoints

### Audit Management
- `POST /api/start-audit` - Start new audit
- `GET /api/audit/{id}/status` - Get audit progress
- `GET /api/audit/{id}/issues` - List discovered issues
- `GET /api/audit/{id}/pages` - List discovered pages
- `GET /api/audit/{id}/report` - Complete audit report

### Document Management
- `POST /api/upload-company-pdfs` - Upload legal PDFs
- `GET /api/company/{id}/documents` - List company documents

### Real-time
- `WS /ws/audit/{id}` - WebSocket for live updates

## Deployment

### Railway Deployment

1. Connect GitHub repo to Railway
2. Add environment variables in Railway dashboard
3. Deploy FastAPI and React separately as services
4. Connect to Supabase

### Docker Build

```bash
cd backend
docker build -t shield-agent .
docker run -p 8000:8000 --env-file .env shield-agent
```

## Troubleshooting

### Backend Won't Start
- Check Python version (3.9+)
- Verify all dependencies installed: `pip list | grep -E "fastapi|playwright|supabase"`
- Check Supabase credentials in .env

### WebSocket Connection Fails
- Ensure backend is running on localhost:8000
- Check browser console for CORS errors
- Verify CORS_ORIGINS in config.py includes your frontend URL

### No Pages Discovered
- Check target URL is accessible
- Verify Playwright browsers installed: `playwright install`
- Check browser console for navigation errors

### LLM Analysis Not Working
- Verify API key set correctly in .env
- Check API quota/billing
- Review logs for rate limiting

## Development Notes

### Adding New Agents
1. Create new class in `crew.py` inheriting agent pattern
2. Implement `async analyze(page_data, audit_page_id)` method
3. Add to orchestrator's parallel execution
4. Create corresponding Supabase table if needed

### Customizing Thresholds
- Edit `backend/config.py` for performance/timing settings
- Adjust agent-specific rules in respective `crew.py` classes
- Update LLM prompts in future version

### Database Migrations
- Create new migration file in `.sql` format
- Execute via Supabase dashboard or CLI
- Always enable RLS for new tables

## Performance Considerations

- BFS traversal capped at 500 pages (configurable)
- Crew agents timeout at 60 seconds per page
- Database queries use indexes for speed
- WebSocket polling frequency: 2 seconds

## Security Notes

- All LLM prompts stored server-side (Prompt Proxy)
- Frontend never sees raw reasoning
- Supabase RLS enforces company data isolation
- Credentials not logged or stored in plaintext
- Screenshots stored in Supabase storage with access controls

## Future Enhancements

- Multi-language support
- Enhanced testimonial fact-checking with external sources
- PDF RAG pipeline for Vault Counsel
- Custom alert configurations
- Automated remediation suggestions
- GitHub issue integration
- Performance profiling
- Accessibility (WCAG) scoring
