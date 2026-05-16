"""
Shield Agent - Web Auditing Platform
Main FastAPI application entry point
"""

import asyncio
import logging
import json
import re
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket, UploadFile, File, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from contextlib import asynccontextmanager
from pydantic import BaseModel
import uuid
from typing import Optional, List

from config import get_settings
from navigator import ShieldNavigator
from crew import CrewOrchestrator
from db import init_supabase

# Configure logging - detailed for debugging Railway 502 issues
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Backend module loading...")

# Global storage for active sessions, WebSocket connections, and Supabase client
active_sessions = {}
active_websockets = {}
supabase = None  # Initialized during app startup in lifespan()

settings = get_settings()

# Wildcard-aware CORS origin checker
_ALLOWED_PATTERNS = [
    re.compile(r'^https?://localhost(:\d+)?$'),
    re.compile(r'^https?://127\.0\.0\.1(:\d+)?$'),
    re.compile(r'^https://[a-z0-9\-]+\.bolt\.new$'),
    re.compile(r'^https://[a-z0-9\-]+\.up\.railway\.app$'),
]
_ALLOWED_EXACT = set(settings.CORS_ORIGINS)

def _is_allowed_origin(origin: str) -> bool:
    if origin in _ALLOWED_EXACT:
        return True
    return any(p.match(origin) for p in _ALLOWED_PATTERNS)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifecycle management"""
    logger.info("="*60)
    logger.info("Shield Agent starting up...")
    logger.info(f"Server: {settings.SERVER_HOST}:{settings.SERVER_PORT}")
    logger.info(f"SUPABASE_URL: {settings.SUPABASE_URL[:50]}..." if settings.SUPABASE_URL else "SUPABASE_URL: MISSING")
    logger.info(f"SUPABASE_KEY: {'*' * 10}" if settings.SUPABASE_KEY else "SUPABASE_KEY: MISSING")
    logger.info(f"SUPABASE_SERVICE_ROLE_KEY: {'set (will be used)' if settings.SUPABASE_SERVICE_ROLE_KEY else 'NOT SET — falling back to SUPABASE_KEY'}")
    logger.info("="*60)

    # Initialize Supabase during startup (not at import time).
    # Do NOT raise here — if Supabase is missing the app still starts and
    # the /health endpoint reports 503, letting Railway health checks pass
    # long enough to see real log errors rather than getting an immediate crash.
    global supabase
    try:
        logger.info("Attempting Supabase initialization...")
        supabase = init_supabase()
        logger.info("SUCCESS: Supabase client initialized")
        logger.info("Backend ready to accept requests")
    except Exception as e:
        logger.error("="*60)
        logger.error("ERROR: Failed to initialize Supabase — audit endpoints will return 503")
        logger.error(f"Reason: {e}")
        logger.error("Set SUPABASE_URL and SUPABASE_KEY in Railway → Variables then redeploy")
        logger.error("="*60)
        supabase = None

    yield

    logger.info("Shield Agent shutting down...")
    for session_id, session in active_sessions.items():
        try:
            await session.get("navigator", {}).close()
        except Exception as e:
            logger.error(f"Error closing session {session_id}: {e}")

app = FastAPI(
    title="Shield Agent API",
    description="Web Auditing Platform - Walk-Through Crew",
    version="1.0.0",
    lifespan=lifespan
)

# Use allow_origins=["*"] so FastAPI doesn't reject anything at middleware level;
# our custom middleware below enforces the actual allowlist including wildcard patterns.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def cors_override(request: Request, call_next):
    """Replace the wildcard CORS header with the actual requesting origin when allowed."""
    origin = request.headers.get("origin", "")
    if request.method == "OPTIONS":
        if origin and _is_allowed_origin(origin):
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Credentials": "true",
                    "Access-Control-Allow-Methods": "*",
                    "Access-Control-Allow-Headers": "*",
                    "Vary": "Origin",
                },
            )
    response = await call_next(request)
    if origin and _is_allowed_origin(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response

# ============== CORE AUDIT ENDPOINTS ==============

class StartAuditRequest(BaseModel):
    target_url: str
    company_id: str
    username: Optional[str] = None
    password: Optional[str] = None
    pdf_file_ids: Optional[List[str]] = None

@app.post("/api/start-audit")
async def start_audit(body: StartAuditRequest):
    """Start a new web audit on target URL"""
    if not supabase:
        logger.error("POST /api/start-audit: Supabase not initialized")
        raise HTTPException(status_code=503, detail="Backend not ready - Supabase unavailable")

    target_url = body.target_url
    company_id = body.company_id
    username = body.username
    password = body.password
    pdf_file_ids = body.pdf_file_ids

    logger.info(f"Starting audit: target={target_url}, company={company_id}")
    try:
        audit_session_id = str(uuid.uuid4())

        now_iso = datetime.now(timezone.utc).isoformat()

        # Create audit session in Supabase
        audit_session = {
            "id": audit_session_id,
            "company_id": company_id,
            "target_url": target_url,
            "status": "running",
            "credentials_used": bool(username and password),
            "username": username,
            "created_at": now_iso,
        }

        response = supabase.table("audit_sessions").insert(audit_session).execute()

        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create audit session")

        # Store session metadata
        active_sessions[audit_session_id] = {
            "target_url": target_url,
            "company_id": company_id,
            "credentials": (username, password) if username and password else None,
            "pdf_file_ids": pdf_file_ids or [],
            "navigator": None,
            "status": "initializing",
            "stop_requested": False,
        }

        # Start audit in background
        asyncio.create_task(run_audit(audit_session_id))

        return {
            "status": "success",
            "audit_session_id": audit_session_id,
            "message": "Audit started successfully"
        }
    except Exception as e:
        logger.error(f"Error starting audit: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/audit/{audit_session_id}/status")
async def get_audit_status(audit_session_id: str):
    """Get current audit status"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Backend not ready - Supabase unavailable")
    try:
        response = supabase.table("audit_sessions").select("*").eq("id", audit_session_id).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="Audit session not found")

        session = response.data[0]
        return {
            "status": session.get("status"),
            "total_pages_discovered": session.get("total_pages_discovered"),
            "total_issues_found": session.get("total_issues_found"),
            "created_at": session.get("created_at"),
            "completed_at": session.get("completed_at"),
        }
    except Exception as e:
        logger.error(f"Error getting audit status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/audit/{audit_session_id}/issues")
async def get_audit_issues(
    audit_session_id: str,
    agent_name: Optional[str] = None,
    severity: Optional[str] = None,
    page_url: Optional[str] = None,
):
    """Get issues for an audit session with optional filtering"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Backend not ready - Supabase unavailable")
    try:
        query = supabase.table("audit_issues").select("*").eq("audit_session_id", audit_session_id)

        if agent_name:
            query = query.eq("agent_name", agent_name)
        if severity:
            query = query.eq("severity", severity)
        if page_url:
            query = query.eq("affected_url", page_url)

        response = query.execute()
        return {"issues": response.data, "total": len(response.data)}
    except Exception as e:
        logger.error(f"Error getting audit issues: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/audit/{audit_session_id}/pages")
async def get_audit_pages(audit_session_id: str):
    """Get discovered pages for an audit session"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Backend not ready - Supabase unavailable")
    try:
        response = supabase.table("audit_pages").select("*").eq("audit_session_id", audit_session_id).execute()
        return {"pages": response.data, "total": len(response.data)}
    except Exception as e:
        logger.error(f"Error getting audit pages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/audit/{audit_session_id}/stop")
async def stop_audit(audit_session_id: str):
    """Request a running audit to stop gracefully"""
    session_data = active_sessions.get(audit_session_id)
    if session_data:
        session_data["stop_requested"] = True
        logger.info(f"Stop requested for audit {audit_session_id}")

    # Mark as stopped in Supabase regardless of whether session is in memory
    # (covers the case where the request hits a fresh worker process)
    if supabase:
        try:
            supabase.table("audit_sessions").update({
                "status": "stopped",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", audit_session_id).in_("status", ["running", "initializing"]).execute()
        except Exception as e:
            logger.error(f"Error marking audit as stopped: {e}")

    return {"status": "stop_requested", "audit_session_id": audit_session_id}

@app.get("/api/audit/{audit_session_id}/report")
async def get_audit_report(audit_session_id: str):
    """Get comprehensive audit report"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Backend not ready - Supabase unavailable")
    try:
        # Fetch all data for report
        session = supabase.table("audit_sessions").select("*").eq("id", audit_session_id).execute()
        pages = supabase.table("audit_pages").select("*").eq("audit_session_id", audit_session_id).execute()
        issues = supabase.table("audit_issues").select("*").eq("audit_session_id", audit_session_id).execute()

        # Organize issues by agent
        issues_by_agent = {}
        for issue in issues.data:
            agent = issue.get("agent_name")
            if agent not in issues_by_agent:
                issues_by_agent[agent] = []
            issues_by_agent[agent].append(issue)

        return {
            "session": session.data[0] if session.data else {},
            "pages": pages.data,
            "issues_by_agent": issues_by_agent,
            "summary": {
                "total_pages": len(pages.data),
                "total_issues": len(issues.data),
                "critical_issues": sum(1 for i in issues.data if i.get("severity") == "critical"),
                "high_issues": sum(1 for i in issues.data if i.get("severity") == "high"),
            }
        }
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============== PDF MANAGEMENT ==============

_PDF_CHUNK_SIZE = 500  # words per chunk
_PDF_CHUNK_OVERLAP = 50  # words of overlap between consecutive chunks


def _chunk_text(text: str, chunk_size: int = _PDF_CHUNK_SIZE, overlap: int = _PDF_CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping word-based chunks."""
    words = text.split()
    chunks = []
    step = chunk_size - overlap
    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk.strip())
        if i + chunk_size >= len(words):
            break
    return chunks


@app.post("/api/upload-company-pdfs")
async def upload_company_pdfs(
    company_id: str,
    files: List[UploadFile] = File(...),
    document_types: Optional[List[str]] = None,
):
    """Upload company legal/policy PDFs, extract text, and store chunks for RAG."""
    import fitz  # PyMuPDF
    if not supabase:
        raise HTTPException(status_code=503, detail="Backend not ready - Supabase unavailable")
    try:
        uploaded_files = []
        for idx, file in enumerate(files):
            file_id = str(uuid.uuid4())
            pdf_bytes = await file.read()

            # Extract full text from all pages
            full_text = ""
            try:
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                for page in doc:
                    full_text += page.get_text() + "\n"
                doc.close()
            except Exception as e:
                logger.warning(f"PDF text extraction failed for {file.filename}: {e}")

            doc_data = {
                "id": file_id,
                "company_id": company_id,
                "file_name": file.filename,
                "file_path": f"documents/{company_id}/{file_id}",
                "document_type": (document_types[idx] if document_types and idx < len(document_types) else "legal"),
                "file_size_bytes": len(pdf_bytes),
            }
            supabase.table("company_documents").insert(doc_data).execute()

            # Chunk and store text for RAG
            if full_text.strip():
                chunks = _chunk_text(full_text)
                chunk_rows = [
                    {
                        "id": str(uuid.uuid4()),
                        "company_document_id": file_id,
                        "chunk_index": i,
                        "chunk_text": chunk,
                    }
                    for i, chunk in enumerate(chunks)
                ]
                if chunk_rows:
                    supabase.table("company_document_embeddings").insert(chunk_rows).execute()
                logger.info(f"Stored {len(chunk_rows)} chunks for document {file.filename}")

            uploaded_files.append({
                "file_id": file_id,
                "filename": file.filename,
                "chunks_stored": len(_chunk_text(full_text)) if full_text.strip() else 0,
            })

        return {"status": "success", "uploaded_files": uploaded_files}
    except Exception as e:
        logger.error(f"Error uploading PDFs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/company/{company_id}/documents")
async def get_company_documents(company_id: str):
    """Get uploaded documents for a company"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Backend not ready - Supabase unavailable")
    try:
        response = supabase.table("company_documents").select("*").eq("company_id", company_id).execute()
        return {"documents": response.data}
    except Exception as e:
        logger.error(f"Error getting documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============== WEBSOCKET STREAMING ==============

@app.websocket("/ws/audit/{audit_session_id}")
async def websocket_audit_stream(websocket: WebSocket, audit_session_id: str):
    """WebSocket connection for real-time audit activity streaming"""
    await websocket.accept()
    active_websockets[audit_session_id] = websocket

    try:
        while True:
            # Keep connection alive and receive any client messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        active_websockets.pop(audit_session_id, None)

async def broadcast_audit_update(audit_session_id: str, message: dict):
    """Broadcast update to all connected WebSocket clients"""
    if audit_session_id in active_websockets:
        try:
            await active_websockets[audit_session_id].send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error broadcasting update: {e}")

# ============== BACKGROUND AUDIT RUNNER ==============

async def run_audit(audit_session_id: str):
    """Main audit execution loop"""
    session_data = active_sessions.get(audit_session_id)

    if not session_data:
        logger.error(f"Session {audit_session_id} not found")
        return

    try:
        logger.info(f"Starting audit {audit_session_id} for {session_data['target_url']}")

        # Initialize navigator and crew
        navigator = ShieldNavigator(
            target_url=session_data["target_url"],
            credentials=session_data["credentials"],
            audit_session_id=audit_session_id,
            supabase_client=supabase,
            broadcast_fn=lambda msg: asyncio.create_task(broadcast_audit_update(audit_session_id, msg)),
            stop_flag_fn=lambda: active_sessions.get(audit_session_id, {}).get("stop_requested", False),
        )

        orchestrator = CrewOrchestrator(
            supabase_client=supabase,
            audit_session_id=audit_session_id,
            broadcast_fn=lambda msg: asyncio.create_task(broadcast_audit_update(audit_session_id, msg)),
        )

        session_data["navigator"] = navigator
        session_data["status"] = "running"

        # Start BFS traversal
        pages = await navigator.start_traversal()

        # Run crew analysis on each PageBundle — check stop flag before each page
        for bundle in pages:
            if session_data.get("stop_requested"):
                logger.info(f"Audit {audit_session_id} stopped by user after navigator phase")
                break
            await orchestrator.analyze_page(bundle)

        # Cross-page consistency checks (pricing, contact ghosting)
        if not session_data.get("stop_requested"):
            await orchestrator.run_post_traversal_pass()

        stopped = session_data.get("stop_requested", False)
        final_status = "stopped" if stopped else "completed"

        # Count total issues for session summary
        total_issues = 0
        if supabase:
            try:
                issues_resp = supabase.table("audit_issues").select("id", count="exact").eq(
                    "audit_session_id", audit_session_id
                ).execute()
                total_issues = issues_resp.count or 0
            except Exception:
                pass

        # Update session as completed/stopped
        if supabase:
            supabase.table("audit_sessions").update({
                "status": final_status,
                "total_pages_discovered": len(pages),
                "total_issues_found": total_issues,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", audit_session_id).execute()

        session_data["status"] = final_status
        logger.info(f"Audit {audit_session_id} {final_status}")

        await broadcast_audit_update(audit_session_id, {
            "type": "audit_complete",
            "audit_session_id": audit_session_id,
            "total_pages": len(pages),
        })

    except Exception as e:
        logger.error(f"Error running audit {audit_session_id}: {e}")

        if supabase:
            try:
                supabase.table("audit_sessions").update({
                    "status": "failed",
                }).eq("id", audit_session_id).execute()
            except Exception as db_err:
                logger.error(f"Failed to mark audit as failed in DB: {db_err}")

        session_data["status"] = "failed"

        await broadcast_audit_update(audit_session_id, {
            "type": "audit_error",
            "audit_session_id": audit_session_id,
            "error": str(e),
        })
    finally:
        # Cleanup
        if session_data.get("navigator"):
            try:
                await session_data["navigator"].close()
            except Exception as e:
                logger.error(f"Error closing navigator: {e}")

# ============== HEALTH CHECK ==============

@app.get("/")
@app.get("/health")
async def health_check():
    """Health check endpoint.
    Always returns 200 so Railway's proxy keeps routing traffic.
    Reports supabase status in the body so you can see it in logs.
    """
    return {
        "status": "ok",
        "service": "Shield Agent API",
        "supabase": "connected" if supabase else "unavailable — set SUPABASE_URL and SUPABASE_KEY in Railway Variables",
        "port": settings.SERVER_PORT,
    }

if __name__ == "__main__":
    import os
    import uvicorn
    # Railway injects PORT at runtime; config.py already reads it but we re-read
    # here so the __main__ guard always uses the live env value even if the cached
    # Settings object was created before Railway set the variable.
    port = int(os.environ.get("PORT", settings.SERVER_PORT))
    uvicorn.run(
        app,
        host=settings.SERVER_HOST,
        port=port,
        log_level=settings.LOG_LEVEL.lower(),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
