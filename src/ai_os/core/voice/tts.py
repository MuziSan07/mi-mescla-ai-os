"""
AI-OS Voice — Text-to-Speech (local, free, female voice via Piper)

Runs Piper as a subprocess (stable across Piper versions). Piper is installed by
the `piper-tts` pip package (provides a `piper` console script) and needs a voice
model file (`<name>.onnx` + `<name>.onnx.json`). A good free female voice is
`en_US-amy-medium`.

Config via env:
  PIPER_BIN           piper executable            (default: "piper")
  PIPER_VOICE_MODEL   path to a .onnx voice model (default: auto-detect in voices dir)
  PIPER_VOICES_DIR    where voice models live     (default: "./voices" or /opt/aios/voices)
"""

import os
import sys
import glob
import shutil
import logging
import tempfile
import subprocess
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Preference order when auto-detecting a female voice model.
_FEMALE_HINTS = ("amy", "female", "jenny", "kathleen", "lessac")


class TextToSpeech:
    """Local text-to-speech via Piper (female voice)."""

    def __init__(self) -> None:
        self.bin = os.getenv("PIPER_BIN", "piper")
        self.voices_dir = os.getenv(
            "PIPER_VOICES_DIR",
            "/opt/aios/voices" if os.path.isdir("/opt/aios/voices") else "voices",
        )
        self.model = os.getenv("PIPER_VOICE_MODEL", "") or self._auto_model()

    # -- discovery ----------------------------------------------------------
    def _auto_model(self) -> str:
        """Pick a voice model from the voices dir, preferring female voices."""
        models = sorted(glob.glob(os.path.join(self.voices_dir, "*.onnx")))
        if not models:
            return ""
        for hint in _FEMALE_HINTS:
            for m in models:
                if hint in os.path.basename(m).lower():
                    return m
        return models[0]  # fall back to whatever voice is present

    def _engine_cmd(self) -> Optional[list]:
        """The base command to invoke Piper, or None if not installed."""
        if shutil.which(self.bin):
            return [self.bin]
        try:
            import piper  # noqa: F401
            return [sys.executable, "-m", "piper"]
        except Exception:
            return None

    # -- availability -------------------------------------------------------
    def is_available(self) -> bool:
        return self._engine_cmd() is not None and bool(self.model) and os.path.exists(self.model)

    def status(self) -> Dict[str, Any]:
        engine = self._engine_cmd()
        return {
            "engine": "piper",
            "available": self.is_available(),
            "installed": engine is not None,
            "voice_model": self.model or None,
            "voice_name": os.path.basename(self.model) if self.model else None,
            "voices_dir": self.voices_dir,
        }

    # -- synthesis ----------------------------------------------------------
    def synthesize_to_file(self, text: str) -> str:
        """Render text to a WAV file and return its path."""
        engine = self._engine_cmd()
        if engine is None:
            raise RuntimeError(
                "Piper is not installed. Install with: pip install piper-tts"
            )
        if not self.model or not os.path.exists(self.model):
            raise RuntimeError(
                f"No Piper voice model found (looked in '{self.voices_dir}'). "
                "Download one, e.g. en_US-amy-medium, or set PIPER_VOICE_MODEL."
            )

        out_path = tempfile.mktemp(suffix=".wav")
        cmd = engine + ["--model", self.model, "--output_file", out_path]
        proc = subprocess.run(
            cmd, input=text.encode("utf-8"), capture_output=True
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"Piper failed: {proc.stderr.decode('utf-8', 'ignore')[:300]}"
            )
        return out_path


_tts: Optional[TextToSpeech] = None


def get_tts() -> TextToSpeech:
    """Get the text-to-speech singleton."""
    global _tts
    if _tts is None:
        _tts = TextToSpeech()
    return _tts
