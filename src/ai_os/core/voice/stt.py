"""
AI-OS Voice — Speech-to-Text (local, free)

Wraps faster-whisper. The heavy dependency is imported lazily so the app boots
fine without it; call `is_available()` / `status()` to check before use.

Config via env:
  WHISPER_MODEL       model size or path   (default: "base")
  WHISPER_DEVICE      "cpu" | "cuda"       (default: "cpu")
  WHISPER_COMPUTE     compute type         (default: "int8" on cpu, "float16" cuda)
"""

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SpeechToText:
    """Local speech-to-text via faster-whisper (lazy-loaded)."""

    def __init__(self) -> None:
        self.model_size = os.getenv("WHISPER_MODEL", "base")
        self.device = os.getenv("WHISPER_DEVICE", "cpu")
        default_compute = "float16" if self.device == "cuda" else "int8"
        self.compute_type = os.getenv("WHISPER_COMPUTE", default_compute)
        self._model = None  # lazily created WhisperModel

    # -- availability -------------------------------------------------------
    @staticmethod
    def is_available() -> bool:
        """True if faster-whisper is importable."""
        try:
            import faster_whisper  # noqa: F401
            return True
        except Exception:
            return False

    def status(self) -> Dict[str, Any]:
        return {
            "engine": "faster-whisper",
            "available": self.is_available(),
            "loaded": self._model is not None,
            "model": self.model_size,
            "device": self.device,
            "compute_type": self.compute_type,
        }

    # -- model --------------------------------------------------------------
    def _ensure_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel  # heavy import, lazy
            logger.info("Loading Whisper model '%s' (%s/%s)...",
                        self.model_size, self.device, self.compute_type)
            self._model = WhisperModel(
                self.model_size, device=self.device, compute_type=self.compute_type
            )
            logger.info("Whisper model ready")
        return self._model

    # -- transcription ------------------------------------------------------
    def transcribe_file(self, path: str, language: Optional[str] = None) -> Dict[str, Any]:
        """Transcribe an audio file (any ffmpeg-decodable format) to text."""
        model = self._ensure_model()
        segments, info = model.transcribe(path, language=language, beam_size=1)
        text = "".join(seg.text for seg in segments).strip()
        return {
            "text": text,
            "language": getattr(info, "language", language),
            "duration": getattr(info, "duration", None),
        }


_stt: Optional[SpeechToText] = None


def get_stt() -> SpeechToText:
    """Get the speech-to-text singleton."""
    global _stt
    if _stt is None:
        _stt = SpeechToText()
    return _stt
