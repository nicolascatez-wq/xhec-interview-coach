"""
X-HEC Interview Coach - FastAPI Backend
Voice-to-voice interview training agent for X-HEC Entrepreneurs candidates.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel

from services.session import SessionMode, session_manager
from services.file_parser import parse_pdf
from services.mistral_agent import get_coach
from services.questions_db import get_interview_questions, get_questions_db
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
    version="1.0.0"
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


class MessageRequest(BaseModel):
    session_id: str
    message: str
    is_presentation: bool = False


class FeedbackRequest(BaseModel):
    session_id: str
    question: str
    response: str


# ============ Startup Events ============

@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    print("🚀 Starting X-HEC Interview Coach...")
    
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
        print("   The app will work but with cached/empty context")


# ============ Root & Static Routes ============

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>X-HEC Interview Coach</h1><p>Frontend not found. Please add static/index.html</p>")


# ============ File Upload Routes ============

@app.post("/api/upload")
async def upload_dossier(
    dossier: UploadFile = File(...)
):
    """
    Upload the candidate's application dossier (PDF).
    
    The dossier should contain the CV and answers to the 5 application questions.
    Interview questions are pre-loaded from the backend database.
    """
    # Validate file type
    if not dossier.filename.lower().endswith('.pdf'):
        raise HTTPException(400, "Le dossier doit être un fichier PDF")
    
    try:
        # Parse dossier PDF
        dossier_content = await dossier.read()
        dossier_text = parse_pdf(dossier_content)
        
        if not dossier_text or len(dossier_text.strip()) < 50:
            raise HTTPException(400, "Le dossier semble vide ou invalide. Veuillez vérifier le fichier.")
        
        # Get questions from database
        questions_db = get_questions_db()
        questions_list = questions_db.get_all_questions()
        
        return {
            "success": True,
            "dossier_preview": dossier_text[:500] + "..." if len(dossier_text) > 500 else dossier_text,
            "questions_count": len(questions_list),
            # Store for session creation
            "_dossier_text": dossier_text,
            "_questions_list": questions_list
        }
        
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erreur lors du traitement du dossier: {str(e)}")


# ============ Session Routes ============

@app.post("/api/session/create")
async def create_session(
    mode: str = Form(...),
    dossier_text: str = Form(...)
):
    """Create a new coaching session."""
    try:
        session_mode = SessionMode(mode)
    except ValueError:
        raise HTTPException(400, f"Mode invalide: {mode}. Utilisez 'question_by_question' ou 'full_interview'")
    
    # Get questions from database
    questions_db = get_questions_db()
    questions_list = questions_db.get_all_questions()
    
    session = session_manager.create_session(
        mode=session_mode,
        cv_content=dossier_text,  # dossier_text contains CV + answers
        questions_list=questions_list,
        user_answers={}  # No separate answers needed, they're in the dossier
    )
    
    return {
        "success": True,
        "session_id": session.id,
        "mode": session.mode.value,
        "questions_count": len(session.questions_list)
    }


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Get session details."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session non trouvée")
    
    return {
        "id": session.id,
        "mode": session.mode.value,
        "is_active": session.is_active,
        "presentation_done": session.presentation_done,
        "questions_answered": len(session.exchanges),
        "total_questions": len(session.questions_list)
    }


@app.delete("/api/session/{session_id}")
async def end_session(session_id: str):
    """End a coaching session."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session non trouvée")
    
    session_manager.end_session(session_id)
    return {"success": True, "message": "Session terminée"}


# ============ Interview Routes ============

@app.post("/api/interview/start")
async def start_interview(request: MessageRequest):
    """
    Start the interview with the candidate's presentation.
    
    The coach will comment briefly and ask the first question.
    """
    session = session_manager.get_session(request.session_id)
    if not session:
        raise HTTPException(404, "Session non trouvée")
    
    if session.presentation_done:
        raise HTTPException(400, "L'entretien a déjà commencé")
    
    try:
        coach = get_coach()
        response = coach.start_interview(session, request.message)
        
        return {
            "success": True,
            "coach_response": response,
            "session_status": {
                "presentation_done": True,
                "mode": session.mode.value
            }
        }
    except Exception as e:
        raise HTTPException(500, f"Erreur lors du démarrage de l'entretien: {str(e)}")


@app.post("/api/interview/respond")
async def respond_to_question(request: FeedbackRequest):
    """
    Process candidate's response to a question.
    
    In Mode 1: Returns immediate feedback
    In Mode 2: Just stores the response, no feedback
    """
    session = session_manager.get_session(request.session_id)
    if not session:
        raise HTTPException(404, "Session non trouvée")
    
    if not session.presentation_done:
        raise HTTPException(400, "L'entretien n'a pas encore commencé")
    
    try:
        coach = get_coach()
        
        if session.mode == SessionMode.QUESTION_BY_QUESTION:
            # Mode 1: Immediate feedback
            feedback = coach.process_response_mode1(session, request.question, request.response)
            return {
                "success": True,
                "feedback": feedback,
                "questions_answered": len(session.exchanges)
            }
        else:
            # Mode 2: No immediate feedback
            coach.process_response_mode2(session, request.question, request.response)
            return {
                "success": True,
                "feedback": None,
                "questions_answered": len(session.exchanges)
            }
            
    except Exception as e:
        raise HTTPException(500, f"Erreur lors du traitement de la réponse: {str(e)}")


@app.post("/api/interview/next-question")
async def get_next_question(session_id: str = Form(...)):
    """Get the next question from the coach."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session non trouvée")
    
    # Check if we've done enough questions for Mode 2 (20 min ~ 8-10 questions)
    if session.mode == SessionMode.FULL_INTERVIEW and len(session.exchanges) >= 10:
        return {
            "success": True,
            "question": None,
            "interview_complete": True,
            "message": "L'entretien de 20 minutes est terminé. Passons au debrief."
        }
    
    try:
        coach = get_coach()
        next_q = coach.get_next_question(session)
        
        if next_q is None:
            return {
                "success": True,
                "question": None,
                "interview_complete": True,
                "message": "Toutes les questions ont été posées."
            }
        
        return {
            "success": True,
            "question": next_q,
            "interview_complete": False,
            "questions_remaining": len(session.questions_list) - len(session.exchanges)
        }
        
    except Exception as e:
        raise HTTPException(500, f"Erreur lors de la génération de la question: {str(e)}")


@app.post("/api/interview/summary")
async def get_summary(session_id: str = Form(...)):
    """Generate the final summary/debrief."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session non trouvée")
    
    if len(session.exchanges) == 0:
        raise HTTPException(400, "Aucune question n'a été répondue")
    
    try:
        coach = get_coach()
        summary = coach.generate_session_summary(session)
        
        return {
            "success": True,
            "summary": summary,
            "questions_answered": len(session.exchanges),
            "mode": session.mode.value
        }
        
    except Exception as e:
        raise HTTPException(500, f"Erreur lors de la génération du résumé: {str(e)}")


@app.get("/api/interview/transcript/{session_id}")
async def get_transcript(session_id: str):
    """Get the full transcript of the session."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session non trouvée")
    
    transcript = session.get_transcript_text()
    
    return {
        "success": True,
        "transcript": transcript,
        "session_id": session_id
    }


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
    """Force a rescrape of pineurs.com (admin only)."""
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
    """Get the current master context (admin only)."""
    context = load_context()
    return {
        "success": True,
        "context": context,
        "text_preview": get_master_context_text()[:1000]
    }


@app.post("/admin/reload-questions")
async def admin_reload_questions():
    """Reload questions from the Excel file."""
    global _questions_db
    from services.questions_db import QuestionsDatabase, _questions_db
    _questions_db = QuestionsDatabase()
    return {
        "success": True,
        "questions_count": _questions_db.get_questions_count()
    }


# ============ Health Check ============

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    db = get_questions_db()
    return {
        "status": "healthy",
        "service": "X-HEC Interview Coach",
        "mistral_configured": bool(os.environ.get("MISTRAL_API_KEY")),
        "questions_loaded": db.get_questions_count()
    }


# ============ Run with uvicorn ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
