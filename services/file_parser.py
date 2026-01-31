"""File parsing utilities for CV (PDF) and Questions (Excel)."""

import io
from typing import Tuple
import pandas as pd
from PyPDF2 import PdfReader


def parse_pdf(file_content: bytes) -> str:
    """
    Extract text content from a PDF file.
    
    Args:
        file_content: Raw bytes of the PDF file
        
    Returns:
        Extracted text content
    """
    try:
        pdf_file = io.BytesIO(file_content)
        reader = PdfReader(pdf_file)
        
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        
        return "\n\n".join(text_parts)
    except Exception as e:
        raise ValueError(f"Erreur lors de la lecture du PDF: {str(e)}")


def parse_excel_questions(file_content: bytes) -> Tuple[list[str], dict[str, str]]:
    """
    Parse an Excel file containing interview questions and user answers.
    
    Expected Excel format:
    - Column 'question' or 'Question': The interview questions
    - Column 'reponse' or 'Reponse' or 'answer' (optional): User's prepared answers
    - Column 'theme' or 'Theme' (optional): Question theme/category
    
    Args:
        file_content: Raw bytes of the Excel file
        
    Returns:
        Tuple of (list of questions, dict mapping questions to answers)
    """
    try:
        excel_file = io.BytesIO(file_content)
        df = pd.read_excel(excel_file)
        
        # Normalize column names
        df.columns = df.columns.str.lower().str.strip()
        
        # Find question column
        question_col = None
        for col in ['question', 'questions', 'q']:
            if col in df.columns:
                question_col = col
                break
        
        if question_col is None:
            # Try first column as questions
            question_col = df.columns[0]
        
        # Find answer column
        answer_col = None
        for col in ['reponse', 'réponse', 'reponses', 'réponses', 'answer', 'answers', 'r']:
            if col in df.columns:
                answer_col = col
                break
        
        # Extract questions
        questions = df[question_col].dropna().astype(str).tolist()
        questions = [q.strip() for q in questions if q.strip()]
        
        # Extract answers if available
        answers = {}
        if answer_col:
            for _, row in df.iterrows():
                q = str(row[question_col]).strip() if pd.notna(row[question_col]) else ""
                a = str(row[answer_col]).strip() if pd.notna(row.get(answer_col)) else ""
                if q and a:
                    answers[q] = a
        
        return questions, answers
        
    except Exception as e:
        raise ValueError(f"Erreur lors de la lecture du fichier Excel: {str(e)}")


def validate_cv(cv_text: str) -> bool:
    """
    Basic validation that the CV contains meaningful content.
    
    Args:
        cv_text: Extracted text from CV
        
    Returns:
        True if CV appears valid
    """
    if not cv_text or len(cv_text.strip()) < 100:
        return False
    
    # Check for common CV keywords
    keywords = ['expérience', 'experience', 'formation', 'education', 
                'compétence', 'skill', 'projet', 'project']
    cv_lower = cv_text.lower()
    
    return any(kw in cv_lower for kw in keywords)


def validate_questions(questions: list[str]) -> bool:
    """
    Validate that questions list is usable.
    
    Args:
        questions: List of questions
        
    Returns:
        True if questions appear valid
    """
    if not questions or len(questions) < 3:
        return False
    
    # Check that questions are actual questions (contain ?)
    question_count = sum(1 for q in questions if '?' in q)
    return question_count >= len(questions) * 0.5  # At least 50% should have ?
