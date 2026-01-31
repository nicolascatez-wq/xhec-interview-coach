"""Mistral AI agent for interview coaching."""

import os
from typing import Optional

from mistralai import Mistral

from prompts.coach_prompt import (
    COACH_SYSTEM_PROMPT,
    FEEDBACK_IMMEDIATE_PROMPT,
    FEEDBACK_GLOBAL_PROMPT,
    QUESTION_INTRO_PROMPT,
    NEXT_QUESTION_PROMPT
)
from services.scraper import get_master_context_text
from services.session import Session, SessionMode


class InterviewCoach:
    """Mistral-powered interview coach for X-HEC candidates."""
    
    def __init__(self):
        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY environment variable not set")
        
        self.client = Mistral(api_key=api_key)
        self.model = "mistral-large-latest"
    
    def _build_system_prompt(self, session: Session) -> str:
        """Build the full system prompt with context."""
        master_context = get_master_context_text()
        
        # Format user answers
        user_answers_text = "\n".join([
            f"Q: {q}\nR: {a}" 
            for q, a in session.user_answers.items()
        ]) if session.user_answers else "Aucune réponse préparée fournie."
        
        return COACH_SYSTEM_PROMPT.format(
            master_context=master_context,
            cv_content=session.cv_content,
            user_answers=user_answers_text
        )
    
    def _chat(self, system_prompt: str, user_message: str) -> str:
        """Send a chat message to Mistral."""
        response = self.client.chat.complete(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        )
        return response.choices[0].message.content
    
    def _chat_with_history(self, system_prompt: str, messages: list[dict]) -> str:
        """Send a chat with message history to Mistral."""
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        response = self.client.chat.complete(
            model=self.model,
            messages=full_messages
        )
        return response.choices[0].message.content
    
    def start_interview(self, session: Session, presentation: str) -> str:
        """
        Start the interview after the candidate's presentation.
        
        Args:
            session: The coaching session
            presentation: Candidate's oral presentation
            
        Returns:
            Coach's response with first question
        """
        session.presentation_done = True
        session.presentation_content = presentation
        
        system_prompt = self._build_system_prompt(session)
        
        # Get remaining questions
        questions_text = "\n".join([f"- {q}" for q in session.questions_list])
        
        prompt = QUESTION_INTRO_PROMPT.format(
            presentation=presentation,
            questions_list=questions_text
        )
        
        return self._chat(system_prompt, prompt)
    
    def process_response_mode1(self, session: Session, question: str, response: str) -> str:
        """
        Process a response in Mode 1 (question by question with immediate feedback).
        
        Args:
            session: The coaching session
            question: The question that was asked
            response: Candidate's response
            
        Returns:
            Immediate feedback
        """
        system_prompt = self._build_system_prompt(session)
        
        prompt = FEEDBACK_IMMEDIATE_PROMPT.format(
            question=question,
            response=response
        )
        
        feedback = self._chat(system_prompt, prompt)
        
        # Store the exchange
        session.add_exchange(question, response, feedback)
        
        return feedback
    
    def process_response_mode2(self, session: Session, question: str, response: str):
        """
        Process a response in Mode 2 (full interview, no immediate feedback).
        
        Args:
            session: The coaching session
            question: The question that was asked
            response: Candidate's response
        """
        # Just store the exchange without feedback
        session.add_exchange(question, response, feedback=None)
    
    def get_next_question(self, session: Session) -> Optional[str]:
        """
        Get the next question from the coach.
        
        Args:
            session: The coaching session
            
        Returns:
            Next question or None if no more questions
        """
        if not session.exchanges:
            return None
        
        system_prompt = self._build_system_prompt(session)
        
        # Get last exchange
        last_exchange = session.exchanges[-1]
        
        # Get remaining questions
        asked_questions = {e.question for e in session.exchanges}
        remaining = [q for q in session.questions_list if q not in asked_questions]
        
        if not remaining:
            return None
        
        remaining_text = "\n".join([f"- {q}" for q in remaining[:5]])  # Limit to 5
        
        feedback_text = ""
        if session.mode == SessionMode.QUESTION_BY_QUESTION and last_exchange.feedback:
            feedback_text = f"\nTon feedback précédent : {last_exchange.feedback}"
        
        prompt = NEXT_QUESTION_PROMPT.format(
            last_question=last_exchange.question,
            last_response=last_exchange.response,
            feedback_if_mode1=feedback_text,
            remaining_questions=remaining_text
        )
        
        return self._chat(system_prompt, prompt)
    
    def generate_final_summary(self, session: Session) -> str:
        """
        Generate the final summary/debrief for Mode 2.
        
        Args:
            session: The coaching session
            
        Returns:
            Complete debrief text
        """
        system_prompt = self._build_system_prompt(session)
        
        # Format all exchanges
        exchanges_text = []
        for i, exchange in enumerate(session.exchanges, 1):
            exchanges_text.append(f"Question {i}: {exchange.question}")
            exchanges_text.append(f"Réponse: {exchange.response}")
            exchanges_text.append("")
        
        prompt = FEEDBACK_GLOBAL_PROMPT.format(
            all_exchanges="\n".join(exchanges_text)
        )
        
        summary = self._chat(system_prompt, prompt)
        session.final_summary = summary
        
        return summary
    
    def generate_session_summary(self, session: Session) -> str:
        """
        Generate a summary for Mode 1 (at the end of question-by-question).
        
        Args:
            session: The coaching session
            
        Returns:
            Session summary
        """
        if session.mode == SessionMode.FULL_INTERVIEW:
            return self.generate_final_summary(session)
        
        # For Mode 1, generate a lighter summary
        system_prompt = self._build_system_prompt(session)
        
        exchanges_text = []
        for i, exchange in enumerate(session.exchanges, 1):
            exchanges_text.append(f"Q{i}: {exchange.question}")
            exchanges_text.append(f"R: {exchange.response}")
            exchanges_text.append(f"Feedback: {exchange.feedback or 'N/A'}")
            exchanges_text.append("")
        
        prompt = f"""Voici le résumé de la session d'entraînement :

{chr(10).join(exchanges_text)}

Génère un bref résumé de fin de session (5-6 lignes max) avec :
- Les points forts de cette session
- 2-3 conseils prioritaires pour la suite
- Un mot d'encouragement

Sois concis et actionnable."""
        
        summary = self._chat(system_prompt, prompt)
        session.final_summary = summary
        
        return summary


# Global coach instance
coach: Optional[InterviewCoach] = None


def get_coach() -> InterviewCoach:
    """Get or create the interview coach instance."""
    global coach
    if coach is None:
        coach = InterviewCoach()
    return coach
