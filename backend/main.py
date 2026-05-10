"""
Shield Agent - Web Auditing Platform
Main FastAPI application entry point
"""

import asyncio
import logging
import json
from fastapi import FastAPI, WebSocket, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager
import uuid
from typing import Optional, List

from config import get_settings
from navigator import ShieldNavigator
from crew import CrewOrchestrator
from db import init_supabase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global storage for active sessions and WebSocket connections
active_sessions = {}
active_websockets = {}

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifecycle management"""
    logger.info("Shield Agent starting up...")
    yield
    logger.info("Shield Agent shutting down...")
    # Cleanup active sessions
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

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase
supabase = init_supabase()

# ============== CORE AUDIT ENDPOINTS ==============

@app.post("/api/start-audit")
async def start_audit(
    target_url: str,
    company_id: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    pdf_file_ids: Optional[List[str]] = None,
):
    """
    Start a new web audit on target URL

    Args:
        target_url: The website URL to audit
        company_id: Company performing the audit
        username: Optional credentials username
        password: Optional credentials password
        pdf_file_ids: Optional list of company document IDs for RAG
    """
    try:
        audit_session_id = str(uuid.uuid4())

        # Create audit session in Supabase
        audit_session = {
            "id": audit_session_id,
            "company_id": company_id,
            "target_url": target_url,
            "status": "running",
            "credentials_used": bool(username and password),
            "username": username,
            "created_at": "now()",
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
    try:
        response = supabase.table("audit_pages").select("*").eq("audit_session_id", audit_session_id).execute()
        return {"pages": response.data, "total": len(response.data)}
    except Exception as e:
        logger.error(f"Error getting audit pages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/audit/{audit_session_id}/report")
async def get_audit_report(audit_session_id: str):
    """Get comprehensive audit report"""
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

@app.post("/api/upload-company-pdfs")
async def upload_company_pdfs(
    company_id: str,
    files: List[UploadFile] = File(...),
    document_types: Optional[List[str]] = None,
):
    """Upload company legal/policy PDFs for RAG pipeline"""
    try:
        uploaded_files = []
        for file in files:
            # Store file in Supabase storage and database
            file_id = str(uuid.uuid4())

            # For now, just store metadata
            doc_data = {
                "id": file_id,
                "company_id": company_id,
                "file_name": file.filename,
                "file_path": f"documents/{company_id}/{file_id}",
                "document_type": document_types[uploaded_files.__len__()] if document_types else "legal",
                "file_size_bytes": file.size,
            }

            supabase.table("company_documents").insert(doc_data).execute()
            uploaded_files.append({"file_id": file_id, "filename": file.filename})

        return {"status": "success", "uploaded_files": uploaded_files}
    except Exception as e:
        logger.error(f"Error uploading PDFs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/company/{company_id}/documents")
async def get_company_documents(company_id: str):
    """Get uploaded documents for a company"""
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
        del active_websockets[audit_session_id]

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

        # Run crew analysis on each page
        for page in pages:
            await orchestrator.analyze_page(page)

        # Update session as completed
        supabase.table("audit_sessions").update({
            "status": "completed",
            "total_pages_discovered": len(pages),
            "completed_at": "now()",
        }).eq("id", audit_session_id).execute()

        session_data["status"] = "completed"
        logger.info(f"Audit {audit_session_id} completed successfully")

        await broadcast_audit_update(audit_session_id, {
            "type": "audit_complete",
            "audit_session_id": audit_session_id,
            "total_pages": len(pages),
        })

    except Exception as e:
        logger.error(f"Error running audit {audit_session_id}: {e}")

        supabase.table("audit_sessions").update({
            "status": "failed",
        }).eq("id", audit_session_id).execute()

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

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "Shield Agent API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        log_level=settings.LOG_LEVEL.lower(),
    )
