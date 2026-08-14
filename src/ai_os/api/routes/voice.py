"""
AI-OS Voice API — speech in, speech out.

Endpoints (mounted at /api/v1/voice):
  GET  /status       availability of STT / TTS engines
  POST /transcribe   audio file  -> {text}
  POST /speak        {text}      -> WAV audio
  POST /chat         audio file  -> transcribe -> hybrid LLM -> speak (JSON w/ base64 wav)

The heavy engines load lazily; if they're not installed the endpoints return a
clear 503 rather than crashing the app.
"""

import os
import base64
import logging

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ai_os.core.voice.stt import get_stt
from ai_os.core.voice.tts import get_tts
from ai_os.core.router.api_gateway import get_unified_gateway

router = APIRouter(tags=["voice"])  # prefix supplied by main.py (/api/v1/voice)
logger = logging.getLogger(__name__)

VOICE_SYSTEM_PROMPT = (
    "You are AI-OS, a friendly female voice assistant. Reply in a natural, "
    "concise, spoken style — a sentence or two, no markdown or code blocks "
    "unless explicitly asked."
)


class SpeakRequest(BaseModel):
    text: str


def _save_upload(audio: UploadFile) -> str:
    """Persist an uploaded audio file to a temp path and return it."""
    import tempfile
    suffix = os.path.splitext(audio.filename or "")[1] or ".webm"
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(audio.file.read())
    return path


@router.get("/status")
async def voice_status():
    """Report whether speech-to-text and text-to-speech are ready."""
    stt, tts = get_stt(), get_tts()
    s, t = stt.status(), tts.status()
    return {
        "stt": s,
        "tts": t,
        "ready": s["available"] and t["available"],
        "hint": None if (s["available"] and t["available"]) else
                "Install voice deps: pip install '.[voice]' and download a Piper voice model.",
    }


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...), language: str = Form(None)):
    """Transcribe an uploaded audio clip to text."""
    stt = get_stt()
    if not stt.is_available():
        raise HTTPException(503, "Speech-to-text not installed (pip install faster-whisper).")
    path = _save_upload(audio)
    try:
        return stt.transcribe_file(path, language=language)
    except Exception as e:
        logger.exception("Transcription failed")
        raise HTTPException(500, f"Transcription failed: {e}")
    finally:
        _cleanup(path)


@router.post("/speak")
async def speak(request: SpeakRequest):
    """Synthesize speech (WAV) from text using the Piper female voice."""
    tts = get_tts()
    if not tts.is_available():
        raise HTTPException(503, "Text-to-speech not ready (install piper-tts + a voice model).")
    if not request.text.strip():
        raise HTTPException(422, "No text to speak.")
    try:
        wav = tts.synthesize_to_file(request.text)
    except Exception as e:
        logger.exception("Speech synthesis failed")
        raise HTTPException(500, f"Speech synthesis failed: {e}")
    return FileResponse(wav, media_type="audio/wav", filename="speech.wav")


@router.post("/chat")
async def voice_chat(audio: UploadFile = File(...), model: str = Form(None)):
    """Full loop: hear -> think (hybrid LLM) -> speak.

    Returns JSON with the transcript, the reply text, and the reply as base64 WAV
    (audio omitted if TTS isn't available, so text still works).
    """
    stt = get_stt()
    if not stt.is_available():
        raise HTTPException(503, "Speech-to-text not installed (pip install faster-whisper).")

    path = _save_upload(audio)
    try:
        transcript = stt.transcribe_file(path)["text"]
    except Exception as e:
        logger.exception("Transcription failed")
        raise HTTPException(500, f"Transcription failed: {e}")
    finally:
        _cleanup(path)

    if not transcript.strip():
        raise HTTPException(422, "Could not hear any speech in the audio.")

    # Think — reuse the hybrid gateway (local Ollama + optional free cloud).
    gateway = get_unified_gateway()
    model_name = model or os.getenv("DEFAULT_LOCAL_MODEL", "llama3.2")
    try:
        result = await gateway.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": VOICE_SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
            temperature=0.6,
            max_tokens=300,
        )
        reply = ""
        if result.choices:
            reply = result.choices[0].get("message", {}).get("content", "") or ""
        reply = reply.strip()
    except Exception as e:
        logger.warning("Voice chat LLM failed: %s", e)
        raise HTTPException(503, f"Assistant unavailable: {e}")

    # Speak — best-effort; text still returns if TTS isn't ready.
    audio_b64 = None
    tts = get_tts()
    if tts.is_available() and reply:
        try:
            wav = tts.synthesize_to_file(reply)
            with open(wav, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode("ascii")
            _cleanup(wav)
        except Exception as e:
            logger.warning("TTS failed (returning text only): %s", e)

    return {
        "transcript": transcript,
        "reply": reply,
        "model": result.model,
        "audio_base64": audio_b64,
        "audio_format": "wav" if audio_b64 else None,
    }


def _cleanup(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
