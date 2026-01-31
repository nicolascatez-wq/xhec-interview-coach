"""
Questions database - Pre-loaded interview questions for X-HEC.
Questions are loaded from an Excel file in the data folder.
"""

import io
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"
QUESTIONS_FILE = DATA_DIR / "questions.xlsx"


class QuestionsDatabase:
    """Manages the pre-loaded interview questions."""
    
    def __init__(self):
        self.questions: List[Dict] = []
        self.load_questions()
    
    def load_questions(self):
        """Load questions from the Excel file."""
        if not QUESTIONS_FILE.exists():
            print(f"⚠️ Questions file not found: {QUESTIONS_FILE}")
            print("   Using default questions...")
            self.questions = self._get_default_questions()
            return
        
        try:
            df = pd.read_excel(QUESTIONS_FILE)
            df.columns = df.columns.str.lower().str.strip()
            
            # Find question column
            question_col = None
            for col in ['question', 'questions', 'q']:
                if col in df.columns:
                    question_col = col
                    break
            
            if question_col is None:
                question_col = df.columns[0]
            
            # Find optional columns
            theme_col = None
            for col in ['theme', 'thème', 'category', 'categorie']:
                if col in df.columns:
                    theme_col = col
                    break
            
            difficulty_col = None
            for col in ['difficulte', 'difficulté', 'difficulty', 'niveau']:
                if col in df.columns:
                    difficulty_col = col
                    break
            
            # Build questions list
            self.questions = []
            for _, row in df.iterrows():
                q_text = str(row[question_col]).strip() if pd.notna(row[question_col]) else ""
                if not q_text:
                    continue
                
                question = {
                    "question": q_text,
                    "theme": str(row[theme_col]).strip() if theme_col and pd.notna(row.get(theme_col)) else "Général",
                    "difficulty": str(row[difficulty_col]).strip() if difficulty_col and pd.notna(row.get(difficulty_col)) else "Moyen"
                }
                self.questions.append(question)
            
            print(f"✅ Loaded {len(self.questions)} questions from database")
            
        except Exception as e:
            print(f"⚠️ Error loading questions: {e}")
            print("   Using default questions...")
            self.questions = self._get_default_questions()
    
    def _get_default_questions(self) -> List[Dict]:
        """Return default questions if Excel file is not available."""
        return [
            {"question": "Pourquoi souhaitez-vous rejoindre le programme X-HEC Entrepreneurs ?", "theme": "Motivation", "difficulty": "Facile"},
            {"question": "Parlez-moi de votre projet entrepreneurial.", "theme": "Projet", "difficulty": "Moyen"},
            {"question": "Quelle est votre plus grande réussite professionnelle ou personnelle ?", "theme": "Parcours", "difficulty": "Moyen"},
            {"question": "Comment gérez-vous l'échec ? Donnez un exemple concret.", "theme": "Soft Skills", "difficulty": "Difficile"},
            {"question": "Où vous voyez-vous dans 5 ans ?", "theme": "Vision", "difficulty": "Moyen"},
            {"question": "Quelles compétences pensez-vous développer grâce à ce programme ?", "theme": "Motivation", "difficulty": "Facile"},
            {"question": "Comment votre parcours vous a-t-il préparé à l'entrepreneuriat ?", "theme": "Parcours", "difficulty": "Moyen"},
            {"question": "Quel est le plus grand défi que vous avez surmonté ?", "theme": "Soft Skills", "difficulty": "Difficile"},
            {"question": "Comment comptez-vous contribuer à la communauté X-HEC ?", "theme": "Motivation", "difficulty": "Moyen"},
            {"question": "Qu'est-ce qui vous différencie des autres candidats ?", "theme": "Personnel", "difficulty": "Difficile"},
            {"question": "Parlez-moi d'une situation où vous avez dû convaincre quelqu'un.", "theme": "Soft Skills", "difficulty": "Moyen"},
            {"question": "Comment définissez-vous le succès ?", "theme": "Vision", "difficulty": "Moyen"},
        ]
    
    def get_all_questions(self) -> List[str]:
        """Get all questions as a simple list of strings."""
        return [q["question"] for q in self.questions]
    
    def get_questions_by_theme(self, theme: str) -> List[str]:
        """Get questions filtered by theme."""
        return [q["question"] for q in self.questions if q["theme"].lower() == theme.lower()]
    
    def get_random_questions(self, count: int = 10) -> List[str]:
        """Get a random selection of questions."""
        import random
        questions = self.get_all_questions()
        if len(questions) <= count:
            return questions
        return random.sample(questions, count)
    
    def get_questions_count(self) -> int:
        """Get the total number of questions."""
        return len(self.questions)


# Global instance
_questions_db: Optional[QuestionsDatabase] = None


def get_questions_db() -> QuestionsDatabase:
    """Get or create the questions database instance."""
    global _questions_db
    if _questions_db is None:
        _questions_db = QuestionsDatabase()
    return _questions_db


def get_interview_questions(count: int = 10) -> List[str]:
    """Get questions for an interview session."""
    db = get_questions_db()
    return db.get_random_questions(count)


def get_all_questions() -> List[str]:
    """Get all available questions."""
    db = get_questions_db()
    return db.get_all_questions()
