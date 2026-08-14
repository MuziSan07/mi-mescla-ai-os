"""
AI-OS Wake-Word Daemon  (Phase 2b — hands-free "always listening")

Runs on the appliance next to the API. It listens on the microphone, waits for a
wake word (openWakeWord, local + free), records what you say next until you stop,
sends it to the running API's /voice/chat, and plays her spoken reply.

Run:
    python -m ai_os.voice_daemon

Config via env:
    WAKE_WORD          openWakeWord model name   (default: "hey_jarvis")
    WAKE_THRESHOLD     detection threshold 0..1  (default: 0.5)
    AIOS_API           base URL of the API       (default: http://localhost:8080)
    MIC_SPEECH_RMS     speech vs silence cutoff  (default: 350)
    MIC_SILENCE_MS     trailing silence to stop  (default: 900)
    MIC_MAX_SECONDS    max command length        (default: 10)

Custom "Hey <Name>" wake words need a trained openWakeWord model — see
https://github.com/dscripka/openWakeWord (training notebook). The built-in
choices include: hey_jarvis, alexa, hey_mycroft.
"""

import os
import io
import sys
import time
import wave
import logging

logger = logging.getLogger("ai_os.voice_daemon")

SAMPLE_RATE = 16000       # openWakeWord expects 16 kHz mono int16
FRAME = 1280              # 80 ms per frame

WAKE_WORD = os.getenv("WAKE_WORD", "hey_jarvis")
THRESHOLD = float(os.getenv("WAKE_THRESHOLD", "0.5"))
API = os.getenv("AIOS_API", "http://localhost:8080").rstrip("/")
SPEECH_RMS = float(os.getenv("MIC_SPEECH_RMS", "350"))
SILENCE_MS = int(os.getenv("MIC_SILENCE_MS", "900"))
MAX_SECONDS = float(os.getenv("MIC_MAX_SECONDS", "10"))


def _require(mod: str, pip: str):
    try:
        return __import__(mod)
    except Exception:
        sys.exit(
            f"[voice_daemon] Missing '{mod}'. Install the wake extra:\n"
            f"    pip install '.[wake]'   (needs system PortAudio: apt install libportaudio2)\n"
            f"    (or: pip install {pip})"
        )


def _pcm16_to_wav_bytes(pcm, sample_rate=SAMPLE_RATE) -> bytes:
    """Wrap a 1-D int16 numpy array as an in-memory WAV file."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def _record_command(stream, np):
    """After the wake word, capture speech until a stretch of silence."""
    frames = []
    chunk_ms = FRAME / SAMPLE_RATE * 1000
    silence_limit = SILENCE_MS / chunk_ms
    max_chunks = int(MAX_SECONDS * 1000 / chunk_ms)
    silent = 0
    started = False
    for _ in range(max_chunks):
        data, _overflow = stream.read(FRAME)
        mono = data[:, 0] if data.ndim > 1 else data
        frames.append(mono.copy())
        rms = float(np.sqrt(np.mean(mono.astype(np.float32) ** 2)))
        if rms > SPEECH_RMS:
            started, silent = True, 0
        elif started:
            silent += 1
            if silent > silence_limit:
                break
    return np.concatenate(frames) if frames else np.zeros(0, dtype="int16")


def _play_wav_bytes(raw: bytes, sd, np):
    """Play a WAV byte string through the default output device."""
    with wave.open(io.BytesIO(raw), "rb") as w:
        rate = w.getframerate()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="int16")
    sd.play(pcm, rate)
    sd.wait()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    np = _require("numpy", "numpy")
    sd = _require("sounddevice", "sounddevice")
    _require("openwakeword", "openwakeword")

    import httpx
    from openwakeword.model import Model
    import openwakeword

    # Ensure the base + pretrained models exist (idempotent download).
    try:
        openwakeword.utils.download_models()
    except Exception as e:
        logger.warning("Could not pre-download openWakeWord models: %s", e)

    logger.info("Loading wake word '%s' (threshold %.2f)...", WAKE_WORD, THRESHOLD)
    try:
        oww = Model(wakeword_models=[WAKE_WORD], inference_framework="onnx")
    except Exception:
        oww = Model(wakeword_models=[WAKE_WORD])  # fall back to tflite default
    logger.info("Listening on the microphone. Say the wake word to begin. (Ctrl+C to stop)")

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                        blocksize=FRAME) as stream:
        while True:
            data, _overflow = stream.read(FRAME)
            mono = data[:, 0] if data.ndim > 1 else data
            scores = oww.predict(mono)
            if scores.get(WAKE_WORD, 0.0) >= THRESHOLD:
                logger.info("Wake word detected (%.2f) — listening for your command...",
                            scores[WAKE_WORD])
                audio = _record_command(stream, np)
                oww.reset()
                if audio.size < SAMPLE_RATE // 2:   # < 0.5 s → nothing said
                    logger.info("No command heard.")
                    continue
                wav = _pcm16_to_wav_bytes(audio)
                try:
                    t = time.time()
                    r = httpx.post(f"{API}/api/v1/voice/chat",
                                   files={"audio": ("command.wav", wav, "audio/wav")},
                                   timeout=120.0)
                    r.raise_for_status()
                    d = r.json()
                    logger.info("You: %s", d.get("transcript"))
                    logger.info("AI-OS (%.1fs): %s", time.time() - t, d.get("reply"))
                    if d.get("audio_base64"):
                        import base64
                        _play_wav_bytes(base64.b64decode(d["audio_base64"]), sd, np)
                except Exception as e:
                    logger.error("Voice request failed: %s", e)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[voice_daemon] stopped.")
