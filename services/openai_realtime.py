"""
OpenAI Realtime API client for voice-to-voice interview coaching.
Uses WebSocket for low-latency bidirectional audio streaming.
"""

import os
import json
import asyncio
import base64
from typing import Optional, Callable, Any
from dataclasses import dataclass

import websockets
from websockets.client import WebSocketClientProtocol

from services.questions_db import get_questions_db
from services.scraper import get_master_context_text


# OpenAI Realtime API endpoint
OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17"


@dataclass
class RealtimeSession:
    """Tracks state for a realtime interview session."""
    session_id: str
    mode: str  # "question_by_question" or "full_interview"
    dossier_text: str
    questions_list: list[str]
    
    # State
    presentation_done: bool = False
    questions_answered: int = 0
    current_question: Optional[str] = None
    transcript: list[dict] = None
    
    def __post_init__(self):
        if self.transcript is None:
            self.transcript = []
    
    def add_to_transcript(self, role: str, content: str):
        self.transcript.append({"role": role, "content": content})


def build_system_instructions(session: RealtimeSession) -> str:
    """Build the system instructions for the OpenAI Realtime session."""
    
    master_context = get_master_context_text()
    questions_text = "\n".join([f"- {q}" for q in session.questions_list])
    
    mode_instructions = ""
    if session.mode == "question_by_question":
        mode_instructions = """
## MODE ACTUEL : Question par Question
- Après chaque réponse du candidat, donne un FEEDBACK IMMÉDIAT (2-3 phrases max)
- Pointe ce qui est bien et ce qui peut être amélioré
- Puis pose la question suivante
"""
    else:
        mode_instructions = """
## MODE ACTUEL : Simulation 20 minutes
- Enchaîne les questions SANS donner de feedback intermédiaire
- Note mentalement les points forts et faibles
- Tu donneras un debrief complet à la fin (après 8-10 questions)
"""
    
    return f"""Tu es un coach d'entretien exigeant et direct pour le Master X-HEC Entrepreneurs.

## TA PERSONNALITÉ
- SHARP : direct, sans détour, pas de langue de bois
- EXIGEANT : comme un vrai membre du jury X-HEC
- CONSTRUCTIF : tu pointes les faiblesses mais donnes toujours une piste d'amélioration
- Tu parles en FRANÇAIS, de manière professionnelle mais naturelle

## CE QUE TU ATTENDS DES RÉPONSES
Une bonne réponse doit être :
1. COURTE : 1-2 minutes max
2. CLAIRE : Structure évidente
3. IMPACTANTE : Accrocher dès la première phrase
4. STRUCTURÉE : Réponse directe + Exemple concret + Lien avec X-HEC

## CE QUE TU SANCTIONNES
- Les "euuuh", "en fait", "du coup" à répétition
- Les réponses trop longues ou qui tournent en rond
- L'absence d'exemple concret
- L'oubli de faire le lien avec X-HEC
- Les réponses évasives

{mode_instructions}

## CONTEXTE X-HEC
{master_context[:2000]}

## DOSSIER DU CANDIDAT
{session.dossier_text[:3000]}

## QUESTIONS DISPONIBLES
{questions_text}

## CONSIGNES
1. Commence par demander au candidat de se présenter en 2-3 minutes
2. Après sa présentation, fais un bref commentaire puis pose ta première question
3. Continue l'entretien naturellement
4. Parle de manière naturelle et fluide, comme à l'oral
5. Sois encourageant mais exigeant
"""


class OpenAIRealtimeClient:
    """
    Client for OpenAI Realtime API.
    Handles WebSocket connection and audio streaming.
    """
    
    def __init__(self, session: RealtimeSession):
        self.session = session
        self.ws: Optional[WebSocketClientProtocol] = None
        self.api_key = os.environ.get("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        # Callbacks
        self.on_audio: Optional[Callable[[bytes], Any]] = None
        self.on_transcript: Optional[Callable[[str, str], Any]] = None
        self.on_error: Optional[Callable[[str], Any]] = None
        
        # State
        self.is_connected = False
        self.response_in_progress = False
    
    async def connect(self):
        """Establish WebSocket connection to OpenAI Realtime API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1"
        }
        
        try:
            self.ws = await websockets.connect(
                OPENAI_REALTIME_URL,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=20
            )
            self.is_connected = True
            print("✅ Connected to OpenAI Realtime API")
            
            # Configure the session
            await self._configure_session()
            
        except Exception as e:
            print(f"❌ Failed to connect to OpenAI Realtime: {e}")
            raise
    
    async def _configure_session(self):
        """Configure the realtime session with instructions and settings."""
        config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": build_system_instructions(self.session),
                "voice": "alloy",  # Options: alloy, echo, fable, onyx, nova, shimmer
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                }
            }
        }
        
        await self.ws.send(json.dumps(config))
        print("✅ Session configured")
    
    async def send_audio(self, audio_data: bytes):
        """Send audio data to OpenAI."""
        if not self.is_connected or not self.ws:
            return
        
        # Encode audio as base64
        audio_b64 = base64.b64encode(audio_data).decode('utf-8')
        
        message = {
            "type": "input_audio_buffer.append",
            "audio": audio_b64
        }
        
        await self.ws.send(json.dumps(message))
    
    async def commit_audio(self):
        """Commit the audio buffer to trigger processing."""
        if not self.is_connected or not self.ws:
            return
        
        message = {"type": "input_audio_buffer.commit"}
        await self.ws.send(json.dumps(message))
    
    async def cancel_response(self):
        """Cancel the current response (for interruptions)."""
        if not self.is_connected or not self.ws:
            return
        
        message = {"type": "response.cancel"}
        await self.ws.send(json.dumps(message))
        self.response_in_progress = False
    
    async def send_text(self, text: str):
        """Send a text message (for testing or hybrid mode)."""
        if not self.is_connected or not self.ws:
            return
        
        message = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}]
            }
        }
        
        await self.ws.send(json.dumps(message))
        
        # Request a response
        await self.ws.send(json.dumps({"type": "response.create"}))
    
    async def listen(self):
        """Listen for messages from OpenAI and handle them."""
        if not self.ws:
            return
        
        try:
            async for message in self.ws:
                await self._handle_message(json.loads(message))
        except websockets.exceptions.ConnectionClosed:
            print("⚠️ WebSocket connection closed")
            self.is_connected = False
        except Exception as e:
            print(f"❌ Error in listen loop: {e}")
            if self.on_error:
                self.on_error(str(e))
    
    async def _handle_message(self, data: dict):
        """Handle incoming messages from OpenAI."""
        msg_type = data.get("type", "")
        
        if msg_type == "session.created":
            print("✅ Realtime session created")
        
        elif msg_type == "session.updated":
            print("✅ Session updated")
        
        elif msg_type == "response.audio.delta":
            # Received audio chunk
            audio_b64 = data.get("delta", "")
            if audio_b64 and self.on_audio:
                audio_bytes = base64.b64decode(audio_b64)
                await self.on_audio(audio_bytes)
        
        elif msg_type == "response.audio_transcript.delta":
            # Received transcript of AI's speech
            transcript = data.get("delta", "")
            if transcript and self.on_transcript:
                await self.on_transcript("assistant", transcript)
        
        elif msg_type == "conversation.item.input_audio_transcription.completed":
            # Received transcript of user's speech
            transcript = data.get("transcript", "")
            if transcript:
                self.session.add_to_transcript("user", transcript)
                if self.on_transcript:
                    await self.on_transcript("user", transcript)
        
        elif msg_type == "response.done":
            self.response_in_progress = False
            # Extract full transcript if available
            response = data.get("response", {})
            output = response.get("output", [])
            for item in output:
                if item.get("type") == "message":
                    for content in item.get("content", []):
                        if content.get("type") == "audio":
                            transcript = content.get("transcript", "")
                            if transcript:
                                self.session.add_to_transcript("assistant", transcript)
        
        elif msg_type == "response.created":
            self.response_in_progress = True
        
        elif msg_type == "error":
            error = data.get("error", {})
            error_msg = error.get("message", "Unknown error")
            print(f"❌ OpenAI Error: {error_msg}")
            if self.on_error:
                await self.on_error(error_msg)
        
        elif msg_type == "input_audio_buffer.speech_started":
            # User started speaking - can interrupt AI
            if self.response_in_progress:
                await self.cancel_response()
        
        elif msg_type == "input_audio_buffer.speech_stopped":
            # User stopped speaking
            pass
    
    async def disconnect(self):
        """Close the WebSocket connection."""
        if self.ws:
            await self.ws.close()
            self.is_connected = False
            print("🔌 Disconnected from OpenAI Realtime")
    
    def get_transcript(self) -> list[dict]:
        """Get the full conversation transcript."""
        return self.session.transcript


# Store active realtime sessions
_active_sessions: dict[str, OpenAIRealtimeClient] = {}


def get_realtime_client(session_id: str) -> Optional[OpenAIRealtimeClient]:
    """Get an active realtime client by session ID."""
    return _active_sessions.get(session_id)


def register_realtime_client(session_id: str, client: OpenAIRealtimeClient):
    """Register a realtime client."""
    _active_sessions[session_id] = client


def remove_realtime_client(session_id: str):
    """Remove a realtime client."""
    if session_id in _active_sessions:
        del _active_sessions[session_id]
