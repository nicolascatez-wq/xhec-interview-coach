"""
X-HEC Interview Coach - FastAPI Backend
Voice-to-voice interview training with OpenAI Realtime API.
"""

import os
import json
import asyncio
import base64
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from services.session import SessionMode, session_manager
from services.file_parser import parse_pdf
from services.questions_db import get_questions_db
from services.openai_realtime import (
    OpenAIRealtimeClient, 
    RealtimeSession,
    get_realtime_client,
    register_realtime_client,
    remove_realtime_client
)
from services.scraper import (
    update_context_if_needed, 
    force_rescrape, 
    get_master_context_text,
    load_context
)

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="X-HEC Interview Coach",
    description="Agent IA voice-to-voice pour s'entraîner aux entretiens X-HEC Entrepreneurs",
    version="2.0.0"
)

# Mount static files
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Ensure uploads directory exists
UPLOADS_DIR = Path(__file__).parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)


# ============ Pydantic Models ============

class SessionCreate(BaseModel):
    mode: str  # "question_by_question" or "full_interview"


# ============ Startup Events ============

@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    print("🚀 Starting X-HEC Interview Coach v2.0 (OpenAI Realtime)...")
    
    # Check OpenAI API key
    if os.environ.get("OPENAI_API_KEY"):
        print("✅ OpenAI API key configured")
    else:
        print("⚠️ OPENAI_API_KEY not set - Realtime API will not work")
    
    # Load questions database
    try:
        db = get_questions_db()
        print(f"✅ Questions database loaded: {db.get_questions_count()} questions")
    except Exception as e:
        print(f"⚠️ Could not load questions database: {e}")
    
    # Check and update master context if needed
    try:
        updated = update_context_if_needed()
        if updated:
            print("✅ Master context updated from pineurs.com")
        else:
            print("✅ Master context loaded from cache")
    except Exception as e:
        print(f"⚠️ Could not update master context: {e}")


# ============ Root & Static Routes ============

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>X-HEC Interview Coach</h1><p>Frontend not found.</p>")


# ============ File Upload Routes ============

@app.post("/api/upload")
async def upload_dossier(dossier: UploadFile = File(...)):
    """Upload the candidate's application dossier (PDF)."""
    if not dossier.filename.lower().endswith('.pdf'):
        raise HTTPException(400, "Le dossier doit être un fichier PDF")
    
    try:
        dossier_content = await dossier.read()
        dossier_text = parse_pdf(dossier_content)
        
        if not dossier_text or len(dossier_text.strip()) < 50:
            raise HTTPException(400, "Le dossier semble vide ou invalide.")
        
        questions_db = get_questions_db()
        questions_list = questions_db.get_all_questions()
        
        return {
            "success": True,
            "dossier_preview": dossier_text[:500] + "..." if len(dossier_text) > 500 else dossier_text,
            "questions_count": len(questions_list),
            "_dossier_text": dossier_text,
            "_questions_list": questions_list
        }
        
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erreur: {str(e)}")


# ============ Session Routes ============

@app.post("/api/session/create")
async def create_session(mode: str = Form(...), dossier_text: str = Form(...)):
    """Create a new coaching session for Realtime API."""
    import uuid
    
    if mode not in ["question_by_question", "full_interview"]:
        raise HTTPException(400, f"Mode invalide: {mode}")
    
    questions_db = get_questions_db()
    questions_list = questions_db.get_all_questions()
    
    session_id = str(uuid.uuid4())
    
    # Create realtime session object
    realtime_session = RealtimeSession(
        session_id=session_id,
        mode=mode,
        dossier_text=dossier_text,
        questions_list=questions_list
    )
    
    # Store session info for later WebSocket connection
    # The actual OpenAI connection happens in the WebSocket handler
    
    return {
        "success": True,
        "session_id": session_id,
        "mode": mode,
        "questions_count": len(questions_list)
    }


@app.get("/api/session/{session_id}/transcript")
async def get_session_transcript(session_id: str):
    """Get the transcript of a session."""
    client = get_realtime_client(session_id)
    if not client:
        raise HTTPException(404, "Session non trouvée ou non connectée")
    
    transcript = client.get_transcript()
    
    # Format transcript
    formatted = []
    for item in transcript:
        role = "Coach" if item["role"] == "assistant" else "Vous"
        formatted.append(f"{role}: {item['content']}")
    
    return {
        "success": True,
        "transcript": "\n\n".join(formatted),
        "raw": transcript
    }


# ============ WebSocket Endpoint for Realtime Audio ============

# Store session data temporarily (in production, use Redis or similar)
_pending_sessions: dict[str, RealtimeSession] = {}


@app.post("/api/session/prepare")
async def prepare_session(mode: str = Form(...), dossier_text: str = Form(...)):
    """Prepare a session for WebSocket connection."""
    import uuid
    
    if mode not in ["question_by_question", "full_interview"]:
        raise HTTPException(400, f"Mode invalide: {mode}")
    
    questions_db = get_questions_db()
    questions_list = questions_db.get_all_questions()
    
    session_id = str(uuid.uuid4())
    
    realtime_session = RealtimeSession(
        session_id=session_id,
        mode=mode,
        dossier_text=dossier_text,
        questions_list=questions_list
    )
    
    _pending_sessions[session_id] = realtime_session
    
    return {
        "success": True,
        "session_id": session_id,
        "mode": mode,
        "questions_count": len(questions_list)
    }


@app.websocket("/ws/interview/{session_id}")
async def websocket_interview(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time voice interview.
    
    Protocol:
    - Client sends: {"type": "audio", "data": "<base64 PCM audio>"}
    - Client sends: {"type": "text", "data": "<text message>"}
    - Client sends: {"type": "interrupt"}
    - Server sends: {"type": "audio", "data": "<base64 PCM audio>"}
    - Server sends: {"type": "transcript", "role": "user|assistant", "text": "..."}
    - Server sends: {"type": "status", "status": "connected|speaking|listening"}
    - Server sends: {"type": "error", "message": "..."}
    """
    await websocket.accept()
    
    # Get the prepared session
    session = _pending_sessions.pop(session_id, None)
    if not session:
        await websocket.send_json({"type": "error", "message": "Session non trouvée. Créez d'abord une session."})
        await websocket.close()
        return
    
    # Create OpenAI Realtime client
    try:
        client = OpenAIRealtimeClient(session)
        register_realtime_client(session_id, client)
        
        # Set up callbacks
        async def on_audio(audio_bytes: bytes):
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
            await websocket.send_json({"type": "audio", "data": audio_b64})
        
        async def on_transcript(role: str, text: str):
            await websocket.send_json({"type": "transcript", "role": role, "text": text})
        
        async def on_error(error_msg: str):
            await websocket.send_json({"type": "error", "message": error_msg})
        
        client.on_audio = on_audio
        client.on_transcript = on_transcript
        client.on_error = on_error
        
        # Connect to OpenAI
        await client.connect()
        await websocket.send_json({"type": "status", "status": "connected"})
        
        # Start listening task for OpenAI responses
        listen_task = asyncio.create_task(client.listen())
        
        # Handle messages from client
        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type", "")
                
                if msg_type == "audio":
                    # Received audio from client
                    audio_b64 = data.get("data", "")
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        await client.send_audio(audio_bytes)
                
                elif msg_type == "commit":
                    # Client signals end of speech
                    await client.commit_audio()
                
                elif msg_type == "text":
                    # Text input (for testing)
                    text = data.get("data", "")
                    if text:
                        await client.send_text(text)
                
                elif msg_type == "interrupt":
                    # User wants to interrupt AI
                    await client.cancel_response()
                
                elif msg_type == "end":
                    # End session
                    break
                    
        except WebSocketDisconnect:
            print(f"Client disconnected: {session_id}")
        
        finally:
            # Cleanup
            listen_task.cancel()
            await client.disconnect()
            remove_realtime_client(session_id)
            
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
        remove_realtime_client(session_id)
        await websocket.close()


# ============ Questions Routes ============

@app.get("/api/questions")
async def get_questions_list():
    """Get the list of available interview questions."""
    db = get_questions_db()
    return {
        "success": True,
        "questions": db.get_all_questions(),
        "count": db.get_questions_count()
    }


# ============ Admin Routes ============

@app.post("/admin/rescrape")
async def admin_rescrape():
    """Force a rescrape of pineurs.com."""
    try:
        content = force_rescrape()
        return {
            "success": True,
            "message": "Rescrape completed",
            "sections_scraped": list(content.get("sections", {}).keys())
        }
    except Exception as e:
        raise HTTPException(500, f"Rescrape failed: {str(e)}")


@app.get("/admin/context")
async def admin_get_context():
    """Get the current master context."""
    context = load_context()
    return {
        "success": True,
        "context": context,
        "text_preview": get_master_context_text()[:1000]
    }


# ============ Health Check ============

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    db = get_questions_db()
    return {
        "status": "healthy",
        "service": "X-HEC Interview Coach v2.0",
        "openai_configured": bool(os.environ.get("OPENAI_API_KEY")),
        "questions_loaded": db.get_questions_count()
    }


# ============ Run with uvicorn ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
