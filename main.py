"""
X-HEC Interview Coach - FastAPI Backend
Sequential voice flow with Whisper + GPT-4 + TTS.
"""

import os
import uuid
from pathlib import Path
from typing import Optional, List, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, Response
from pydantic import BaseModel

from services.questions_db import get_questions_db
from services.file_parser import parse_pdf
from services.scraper import (
    update_context_if_needed, 
    force_rescrape, 
    get_master_context_text,
    load_context
)
from services.openai_services import (
    transcribe_audio,
    chat_response,
    text_to_speech,
    categorize_questions,
    generate_debrief,
    get_coach_intro,
    get_question_feedback,
    select_next_question
)

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="X-HEC Interview Coach",
    description="Agent IA pour s'entraîner aux entretiens X-HEC Entrepreneurs",
    version="3.0.0"
)

# Mount static files
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Ensure uploads directory exists
UPLOADS_DIR = Path(__file__).parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)


# ============ In-Memory Session Storage ============

class Session:
    def __init__(
        self,
        session_id: str,
        mode: str,
        dossier_text: str
    ):
        self.session_id = session_id
        self.mode = mode
        self.dossier_text = dossier_text
        self.transcript: List[Dict[str, str]] = []
        self.current_theme: Optional[str] = None
        self.current_question: Optional[str] = None
        self.asked_questions: List[str] = []
        self.started = False

_sessions: Dict[str, Session] = {}


# ============ Pydantic Models ============

class ChatMessage(BaseModel):
    role: str
    content: str


# ============ Startup Events ============

@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    print("🚀 Starting X-HEC Interview Coach v3.0 (Sequential Flow)...")
    
    # Check OpenAI API key
    if os.environ.get("OPENAI_API_KEY"):
        print("✅ OpenAI API key configured")
    else:
        print("⚠️ OPENAI_API_KEY not set - API will not work")
    
    # Load questions database
    try:
        db = get_questions_db()
        print(f"✅ Questions database loaded: {db.get_questions_count()} questions")
        
        # Categorize with AI if not already done
        if not db.has_themes():
            await db.categorize_with_ai()
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
        
        return {
            "success": True,
            "dossier_preview": dossier_text[:500] + "..." if len(dossier_text) > 500 else dossier_text,
            "questions_count": questions_db.get_questions_count(),
            "_dossier_text": dossier_text
        }
        
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erreur: {str(e)}")


# ============ Session Routes ============

@app.post("/api/session/create")
async def create_session(mode: str = Form(...), dossier_text: str = Form(...)):
    """Create a new coaching session."""
    if mode not in ["question_by_question", "full_interview"]:
        raise HTTPException(400, f"Mode invalide: {mode}")
    
    session_id = str(uuid.uuid4())
    
    session = Session(
        session_id=session_id,
        mode=mode,
        dossier_text=dossier_text
    )
    _sessions[session_id] = session
    
    return {
        "success": True,
        "session_id": session_id,
        "mode": mode
    }


@app.get("/api/session/{session_id}/intro")
async def get_session_intro(session_id: str):
    """Get the coach's intro message for a session."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session non trouvée")
    
    master_context = get_master_context_text()
    
    intro = await get_coach_intro(session.dossier_text, master_context)
    
    # Add to transcript
    session.transcript.append({"role": "assistant", "content": intro})
    session.started = True
    
    # Generate audio
    audio_bytes = await text_to_speech(intro)
    
    return {
        "success": True,
        "text": intro,
        "audio_base64": __import__('base64').b64encode(audio_bytes).decode('utf-8')
    }


# ============ Themes & Questions Routes ============

@app.get("/api/themes")
async def get_themes():
    """Get available themes with question counts."""
    db = get_questions_db()
    
    # Categorize if not done yet
    if not db.has_themes():
        await db.categorize_with_ai()
    
    return {
        "success": True,
        "themes": db.get_themes_with_counts()
    }


@app.get("/api/themes/{theme}/questions")
async def get_theme_questions(theme: str, session_id: Optional[str] = None):
    """Get questions for a specific theme."""
    db = get_questions_db()
    questions = db.get_questions_by_theme(theme)
    
    if not questions:
        raise HTTPException(404, f"Thème non trouvé: {theme}")
    
    # Filter out already asked questions if session provided
    asked = []
    if session_id:
        session = _sessions.get(session_id)
        if session:
            asked = session.asked_questions
    
    available = [q for q in questions if q not in asked]
    
    return {
        "success": True,
        "theme": theme,
        "questions": available,
        "total": len(questions),
        "available": len(available)
    }


@app.post("/api/session/{session_id}/select-theme")
async def select_theme(session_id: str, theme: str = Form(...)):
    """Select a theme for the session."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session non trouvée")
    
    db = get_questions_db()
    if theme not in db.get_themes():
        raise HTTPException(400, f"Thème invalide: {theme}")
    
    session.current_theme = theme
    
    # Generate coach response about the theme
    questions = db.get_questions_by_theme(theme)
    available = [q for q in questions if q not in session.asked_questions]
    
    response_text = f"Très bien, on va travailler sur le thème « {theme} ». J'ai {len(available)} questions pour toi sur ce sujet. Tu veux que je choisisse une question au hasard, ou tu préfères choisir toi-même ?"
    
    session.transcript.append({"role": "assistant", "content": response_text})
    
    audio_bytes = await text_to_speech(response_text)
    
    return {
        "success": True,
        "text": response_text,
        "audio_base64": __import__('base64').b64encode(audio_bytes).decode('utf-8'),
        "available_questions": available
    }


@app.post("/api/session/{session_id}/select-question")
async def select_question(session_id: str, question: Optional[str] = Form(None), random: bool = Form(False)):
    """Select a specific question or get a random one."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session non trouvée")
    
    if not session.current_theme:
        raise HTTPException(400, "Sélectionne d'abord un thème")
    
    db = get_questions_db()
    available = [q for q in db.get_questions_by_theme(session.current_theme) if q not in session.asked_questions]
    
    if not available:
        return {
            "success": False,
            "message": "Plus de questions disponibles dans ce thème",
            "text": "Tu as fait le tour de ce thème ! Tu veux passer à un autre thème ou faire le débrief ?",
            "audio_base64": __import__('base64').b64encode(
                await text_to_speech("Tu as fait le tour de ce thème ! Tu veux passer à un autre thème ou faire le débrief ?")
            ).decode('utf-8')
        }
    
    if random or not question:
        import random as rand
        question = rand.choice(available)
    elif question not in available:
        raise HTTPException(400, "Question non disponible")
    
    session.current_question = question
    session.asked_questions.append(question)
    
    # Generate coach asking the question
    intro = await select_next_question(
        session.current_theme,
        available,
        session.asked_questions[:-1],  # Exclude current
        session.transcript[-2:] if len(session.transcript) >= 2 else None
    )
    
    session.transcript.append({"role": "assistant", "content": intro})
    
    audio_bytes = await text_to_speech(intro)
    
    return {
        "success": True,
        "question": question,
        "text": intro,
        "audio_base64": __import__('base64').b64encode(audio_bytes).decode('utf-8')
    }


# ============ Audio/Chat Routes ============

@app.post("/api/transcribe")
async def transcribe_audio_endpoint(audio: UploadFile = File(...)):
    """Transcribe audio to text using Whisper."""
    try:
        audio_bytes = await audio.read()
        text = await transcribe_audio(audio_bytes, audio.filename or "audio.webm")
        return {
            "success": True,
            "text": text
        }
    except Exception as e:
        raise HTTPException(500, f"Transcription error: {str(e)}")


@app.post("/api/session/{session_id}/respond")
async def respond_to_session(
    session_id: str,
    user_text: str = Form(...)
):
    """Process user's response and get coach feedback."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session non trouvée")
    
    # Add user response to transcript
    session.transcript.append({"role": "user", "content": user_text})
    
    # Generate feedback based on mode
    if session.mode == "question_by_question" and session.current_question:
        # Immediate feedback mode
        feedback = await get_question_feedback(session.current_question, user_text)
        session.transcript.append({"role": "assistant", "content": feedback})
        
        audio_bytes = await text_to_speech(feedback)
        
        return {
            "success": True,
            "text": feedback,
            "audio_base64": __import__('base64').b64encode(audio_bytes).decode('utf-8'),
            "type": "feedback"
        }
    else:
        # Full interview mode - just acknowledge and continue
        db = get_questions_db()
        
        if session.current_theme:
            available = [q for q in db.get_questions_by_theme(session.current_theme) if q not in session.asked_questions]
        else:
            available = [q for q in db.get_all_questions() if q not in session.asked_questions]
        
        if available:
            next_q = await select_next_question(
                session.current_theme or "Général",
                available,
                session.asked_questions,
                {"question": session.current_question, "response": user_text}
            )
            session.current_question = available[0]  # Track which one was asked
            session.asked_questions.append(available[0])
            session.transcript.append({"role": "assistant", "content": next_q})
            
            audio_bytes = await text_to_speech(next_q)
            
            return {
                "success": True,
                "text": next_q,
                "audio_base64": __import__('base64').b64encode(audio_bytes).decode('utf-8'),
                "type": "next_question"
            }
        else:
            # No more questions
            return {
                "success": True,
                "text": "On a fait le tour ! Tu veux faire le débrief ?",
                "audio_base64": __import__('base64').b64encode(
                    await text_to_speech("On a fait le tour ! Tu veux faire le débrief ?")
                ).decode('utf-8'),
                "type": "end"
            }


@app.post("/api/speak")
async def speak_text(text: str = Form(...)):
    """Convert text to speech."""
    try:
        audio_bytes = await text_to_speech(text)
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=speech.mp3"}
        )
    except Exception as e:
        raise HTTPException(500, f"TTS error: {str(e)}")


# ============ Debrief Routes ============

@app.post("/api/session/{session_id}/debrief")
async def get_session_debrief(session_id: str):
    """Generate the final debrief for a session."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session non trouvée")
    
    if len(session.transcript) < 2:
        raise HTTPException(400, "Pas assez d'échanges pour un débrief")
    
    try:
        debrief = await generate_debrief(session.transcript, session.mode)
        
        # Generate a spoken summary
        summary_text = f"Voici mon analyse de ta session. "
        if debrief.get("note_globale"):
            summary_text += f"Note globale : {debrief['note_globale'].get('score', 'N/A')}. {debrief['note_globale'].get('commentaire', '')} "
        if debrief.get("prochain_objectif"):
            summary_text += f"Pour ta prochaine session, concentre-toi sur : {debrief['prochain_objectif']}"
        
        audio_bytes = await text_to_speech(summary_text)
        
        return {
            "success": True,
            "debrief": debrief,
            "summary_text": summary_text,
            "audio_base64": __import__('base64').b64encode(audio_bytes).decode('utf-8')
        }
    except Exception as e:
        raise HTTPException(500, f"Debrief error: {str(e)}")


@app.get("/api/session/{session_id}/transcript")
async def get_session_transcript(session_id: str):
    """Get the raw transcript of a session."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session non trouvée")
    
    # Format transcript
    formatted = []
    for item in session.transcript:
        role = "Coach" if item["role"] == "assistant" else "Vous"
        formatted.append(f"{role}: {item['content']}")
    
    return {
        "success": True,
        "transcript": "\n\n".join(formatted),
        "raw": session.transcript
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


@app.post("/admin/recategorize")
async def admin_recategorize():
    """Force recategorization of questions."""
    try:
        db = get_questions_db()
        await db.categorize_with_ai()
        return {
            "success": True,
            "themes": db.get_themes_with_counts()
        }
    except Exception as e:
        raise HTTPException(500, f"Recategorize failed: {str(e)}")


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
        "service": "X-HEC Interview Coach v3.0",
        "openai_configured": bool(os.environ.get("OPENAI_API_KEY")),
        "questions_loaded": db.get_questions_count(),
        "themes_loaded": db.has_themes()
    }


# ============ Run with uvicorn ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
