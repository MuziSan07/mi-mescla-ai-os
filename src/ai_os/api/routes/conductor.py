"""
AI-OS Conductor API (Phase 3) — orchestrate specialist agents from one goal.

Endpoints (mounted at /api/v1/conductor):
  GET  /status   specialists + readiness
  POST /run      {goal} -> plan, per-step agent outputs, synthesized answer
  POST /voice    audio  -> transcribe -> conductor -> spoken answer (JSON + base64 wav)
"""

import os
import base64
import logging

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from ai_os.core.orchestrator.conductor import get_conductor, VALID_SPECIALISTS
from ai_os.core.orchestrator.backends import available_backends, selected_backend

router = APIRouter(tags=["conductor"])  # prefix supplied by main.py (/api/v1/conductor)
logger = logging.getLogger(__name__)


class ConductorRequest(BaseModel):
    goal: str
    model: str | None = None
    remember: bool = False   # save the final answer to the knowledge vault


@router.get("/status")
async def conductor_status():
    """Report the Conductor's specialists and active backend."""
    return {
        "conductor": "ready",
        "specialists": VALID_SPECIALISTS,
        "backend": selected_backend(),
        "note": "POST /run with a goal; the Conductor plans, delegates, and synthesizes.",
    }


@router.get("/backends")
async def conductor_backends():
    """Which orchestration frameworks are installed + which is active."""
    return {"active": selected_backend(), "frameworks": available_backends()}


@router.post("/run")
async def conductor_run(request: ConductorRequest):
    """Decompose a goal, delegate to specialist agents, return the full trace."""
    if not request.goal.strip():
        raise HTTPException(422, "Empty goal.")
    conductor = get_conductor()
    try:
        result = await conductor.run(request.goal, model=request.model)
    except Exception as e:
        logger.exception("Conductor run failed")
        raise HTTPException(500, f"Conductor failed: {e}")

    payload = result.to_dict()
    # Optionally persist the answer to the Obsidian vault (shared memory).
    if request.remember and result.answer:
        try:
            from ai_os.core.knowledge.vault import get_vault
            note = get_vault().write_note(request.goal[:60], result.answer, tags=["conductor"])
            payload["saved_note"] = note.path
        except Exception as e:
            logger.warning("Could not save conductor answer to vault: %s", e)
    return payload


@router.post("/voice")
async def conductor_voice(audio: UploadFile = File(...), model: str = Form(None)):
    """Speak a goal, the Conductor orchestrates it, and answers out loud."""
    from ai_os.core.voice.stt import get_stt
    from ai_os.core.voice.tts import get_tts

    stt = get_stt()
    if not stt.is_available():
        raise HTTPException(503, "Speech-to-text not installed (pip install faster-whisper).")

    import tempfile
    suffix = os.path.splitext(audio.filename or "")[1] or ".webm"
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(audio.file.read())
    try:
        goal = stt.transcribe_file(path)["text"].strip()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

    if not goal:
        raise HTTPException(422, "Could not hear any speech.")

    result = await get_conductor().run(goal, model=model)

    audio_b64 = None
    tts = get_tts()
    if tts.is_available() and result.answer:
        try:
            wav = tts.synthesize_to_file(result.answer)
            with open(wav, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode("ascii")
            os.remove(wav)
        except Exception as e:
            logger.warning("TTS failed (text only): %s", e)

    payload = result.to_dict()
    payload["transcript"] = goal
    payload["audio_base64"] = audio_b64
    return payload
