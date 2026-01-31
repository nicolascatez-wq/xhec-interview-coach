"""
OpenAI Services - Whisper, GPT-4, TTS for sequential voice flow.
"""

import os
import json
from typing import List, Dict, Optional
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """
    Transcribe audio using Whisper.
    
    Args:
        audio_bytes: Raw audio bytes (webm, mp3, wav, etc.)
        filename: Filename hint for format detection
    
    Returns:
        Transcribed text
    """
    import io
    
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename
    
    response = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        language="fr"
    )
    
    return response.text


async def chat_response(
    messages: List[Dict[str, str]], 
    system_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 500
) -> str:
    """
    Generate a chat response using GPT-4.
    
    Args:
        messages: Conversation history [{"role": "user/assistant", "content": "..."}]
        system_prompt: System prompt for the coach
        temperature: Creativity level (0-1)
        max_tokens: Max response length
    
    Returns:
        Assistant's response text
    """
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=full_messages,
        temperature=temperature,
        max_tokens=max_tokens
    )
    
    return response.choices[0].message.content


async def text_to_speech(text: str, voice: str = "nova") -> bytes:
    """
    Convert text to speech using OpenAI TTS.
    
    Args:
        text: Text to convert
        voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
    
    Returns:
        Audio bytes (MP3 format)
    """
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
        response_format="mp3"
    )
    
    return response.content


async def categorize_questions(questions: List[str]) -> Dict[str, List[str]]:
    """
    Categorize questions into themes using GPT-4.
    
    Args:
        questions: List of interview questions
    
    Returns:
        Dict mapping theme names to lists of questions
    """
    prompt = f"""Tu dois catégoriser ces questions d'entretien en 4-5 thèmes.

Thèmes suggérés (tu peux les adapter) :
- "Questions chiantes" : les questions difficiles, pièges ou stressantes
- "Questions sur le Master" : tout ce qui concerne X-HEC spécifiquement
- "Questions sur moi" : parcours personnel, motivations, personnalité
- "Questions projet" : projet entrepreneurial, vision business
- "Questions soft skills" : leadership, gestion d'équipe, échec, etc.

Questions à catégoriser :
{json.dumps(questions, ensure_ascii=False, indent=2)}

Réponds UNIQUEMENT en JSON valide avec ce format :
{{
  "themes": {{
    "Nom du thème 1": ["question 1", "question 2"],
    "Nom du thème 2": ["question 3", "question 4"]
  }}
}}

Assure-toi que TOUTES les questions sont catégorisées.
"""
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2000,
        response_format={"type": "json_object"}
    )
    
    result = json.loads(response.choices[0].message.content)
    return result.get("themes", {})


async def generate_debrief(transcript: List[Dict], mode: str) -> Dict:
    """
    Generate an intelligent debrief from the session transcript.
    
    Args:
        transcript: List of exchanges [{"role": "user/assistant", "content": "..."}]
        mode: "question_by_question" or "full_interview"
    
    Returns:
        Structured debrief with strengths, improvements, and advice
    """
    # Format transcript for analysis
    formatted_transcript = "\n\n".join([
        f"{'Coach' if item['role'] == 'assistant' else 'Candidat'}: {item['content']}"
        for item in transcript
    ])
    
    prompt = f"""Tu viens de coacher un candidat pour son entretien X-HEC Entrepreneurs.
Voici le transcript complet de la session :

{formatted_transcript}

---

Génère un DEBRIEF STRUCTURÉ en analysant les réponses du candidat.

Réponds en JSON avec EXACTEMENT ce format :
{{
  "points_forts": [
    {{
      "titre": "Titre court du point fort",
      "detail": "Explication avec exemple de la session"
    }}
  ],
  "points_amelioration": [
    {{
      "titre": "Titre court du point à améliorer", 
      "detail": "Explication avec exemple de la session",
      "conseil": "Conseil concret pour s'améliorer"
    }}
  ],
  "note_globale": {{
    "score": "X/10",
    "commentaire": "Appréciation globale en 2-3 phrases"
  }},
  "prochain_objectif": "Un objectif concret pour la prochaine session"
}}

Sois HONNÊTE et CONSTRUCTIF. Cite des exemples spécifiques de la session.
"""
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=1500,
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)


async def get_coach_intro(dossier_text: str, master_context: str) -> str:
    """
    Generate the coach's intro asking what the user wants to work on.
    
    Returns:
        Coach's opening message
    """
    prompt = f"""Tu es un coach d'entretien X-HEC. Le candidat vient de commencer une session.

Contexte du Master :
{master_context[:500]}...

Extrait du dossier du candidat :
{dossier_text[:500]}...

Commence par te présenter BRIÈVEMENT (1-2 phrases) et demande au candidat ce qu'il veut travailler aujourd'hui.
Propose-lui les options :
- S'entraîner sur des questions par thème
- Faire une simulation d'entretien complète

Sois chaleureux mais professionnel. Max 4-5 phrases au total.
"""
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=200
    )
    
    return response.choices[0].message.content


async def get_question_feedback(question: str, response: str) -> str:
    """
    Generate immediate feedback for a single answer.
    
    Args:
        question: The question that was asked
        response: The candidate's response
    
    Returns:
        Short, direct feedback
    """
    prompt = f"""Analyse cette réponse d'entretien X-HEC et donne un feedback COURT et DIRECT.

Question posée : {question}
Réponse du candidat : {response}

Ton feedback doit :
1. Dire si c'est bien ou pas (1 phrase)
2. Pointer 1-2 problèmes spécifiques si présents
3. Donner UN conseil concret

MAX 4-5 phrases au total. Sois direct comme un vrai coach, pas de langue de bois.
"""
    
    response_obj = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
        max_tokens=200
    )
    
    return response_obj.choices[0].message.content


async def select_next_question(
    theme: str, 
    available_questions: List[str],
    asked_questions: List[str],
    last_exchange: Optional[Dict] = None
) -> str:
    """
    Select the next question based on context.
    
    Args:
        theme: Current theme
        available_questions: Questions in this theme
        asked_questions: Questions already asked
        last_exchange: Previous Q&A if any
    
    Returns:
        The next question to ask (with optional transition)
    """
    remaining = [q for q in available_questions if q not in asked_questions]
    
    if not remaining:
        return None
    
    context = ""
    if last_exchange:
        context = f"""
Échange précédent :
Q: {last_exchange.get('question', '')}
R: {last_exchange.get('response', '')}

Fais une transition naturelle (1 phrase max) puis pose la question suivante.
"""
    
    prompt = f"""Tu es coach d'entretien. Choisis la prochaine question à poser.

Thème actuel : {theme}
{context}

Questions disponibles :
{json.dumps(remaining, ensure_ascii=False)}

Choisis UNE question pertinente et pose-la de manière naturelle, comme à l'oral.
Si c'est la première question, présente brièvement le thème.
"""
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=200
    )
    
    return response.choices[0].message.content
