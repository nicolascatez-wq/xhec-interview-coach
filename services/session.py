"""Session management for interview coaching sessions."""

import uuid
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum


class SessionMode(Enum):
    QUESTION_BY_QUESTION = "question_by_question"
    FULL_INTERVIEW = "full_interview"


@dataclass
class QuestionResponse:
    """Stores a question and its response with feedback."""
    question: str
    response: str
    feedback: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    score: Optional[int] = None  # 1-10
    issues: list[str] = field(default_factory=list)  # e.g., ["tics_verbaux", "pas_exemple"]


@dataclass
class Session:
    """Represents a coaching session."""
    id: str
    mode: SessionMode
    cv_content: str
    questions_list: list[str]
    user_answers: dict[str, str]  # Question answers from Excel
    created_at: datetime
    
    # Session state
    current_question_index: int = 0
    exchanges: list[QuestionResponse] = field(default_factory=list)
    presentation_done: bool = False
    presentation_content: Optional[str] = None
    is_active: bool = True
    
    # Final summary
    final_summary: Optional[str] = None
    transcript: list[dict] = field(default_factory=list)
    
    def add_exchange(self, question: str, response: str, feedback: Optional[str] = None):
        """Add a Q&A exchange to the session."""
        exchange = QuestionResponse(
            question=question,
            response=response,
            feedback=feedback
        )
        self.exchanges.append(exchange)
        self.transcript.append({
            "timestamp": exchange.timestamp.isoformat(),
            "question": question,
            "response": response,
            "feedback": feedback
        })
        
    def get_next_question(self) -> Optional[str]:
        """Get the next question from the list."""
        if self.current_question_index < len(self.questions_list):
            question = self.questions_list[self.current_question_index]
            self.current_question_index += 1
            return question
        return None
    
    def get_random_question(self) -> Optional[str]:
        """Get a random question from the list."""
        import random
        if self.questions_list:
            return random.choice(self.questions_list)
        return None
    
    def get_transcript_text(self) -> str:
        """Generate a text transcript of the session."""
        lines = [f"=== Session d'entraînement X-HEC ==="]
        lines.append(f"Date: {self.created_at.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"Mode: {self.mode.value}")
        lines.append("")
        
        if self.presentation_content:
            lines.append("--- Présentation ---")
            lines.append(self.presentation_content)
            lines.append("")
        
        for i, exchange in enumerate(self.exchanges, 1):
            lines.append(f"--- Question {i} ---")
            lines.append(f"Q: {exchange.question}")
            lines.append(f"R: {exchange.response}")
            if exchange.feedback:
                lines.append(f"Feedback: {exchange.feedback}")
            lines.append("")
        
        if self.final_summary:
            lines.append("--- Résumé Final ---")
            lines.append(self.final_summary)
        
        return "\n".join(lines)


class SessionManager:
    """Manages all active sessions."""
    
    def __init__(self):
        self.sessions: dict[str, Session] = {}
    
    def create_session(
        self,
        mode: SessionMode,
        cv_content: str,
        questions_list: list[str],
        user_answers: dict[str, str]
    ) -> Session:
        """Create a new coaching session."""
        session_id = str(uuid.uuid4())
        session = Session(
            id=session_id,
            mode=mode,
            cv_content=cv_content,
            questions_list=questions_list,
            user_answers=user_answers,
            created_at=datetime.now()
        )
        self.sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieve a session by ID."""
        return self.sessions.get(session_id)
    
    def end_session(self, session_id: str):
        """Mark a session as ended."""
        if session_id in self.sessions:
            self.sessions[session_id].is_active = False
    
    def delete_session(self, session_id: str):
        """Delete a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]


# Global session manager instance
session_manager = SessionManager()
