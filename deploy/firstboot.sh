#!/usr/bin/env bash
# ============================================================================
#  AI-OS first-boot provisioning
#
#  Runs ONCE on the first boot of the AI-OS.iso image to fetch the heavy bits
#  that are deliberately kept OUT of the ISO (to keep it small): the Ollama
#  runtime + default model, and the Piper female voice. After it finishes it
#  marks itself done so it never runs again.
#
#  Invoked by aios-firstboot.service. Needs network.
# ============================================================================
set -u

DONE=/opt/aios/.firstboot-done
[ -f "$DONE" ] && exit 0

# Load config (DEFAULT_LOCAL_MODEL etc.)
if [ -f /opt/aios/app/.env ]; then
    set -a; . /opt/aios/app/.env 2>/dev/null || true; set +a
fi
MODEL="${DEFAULT_LOCAL_MODEL:-llama3.2}"

echo "[firstboot] Installing Ollama..."
if ! command -v ollama >/dev/null 2>&1; then
    curl -fsSL https://ollama.com/install.sh | sh || true
fi
systemctl enable --now ollama || true
sleep 5
echo "[firstboot] Pulling model '${MODEL}' (this can take a while)..."
sudo -u aios ollama pull "${MODEL}" || echo "[firstboot] WARN: model pull failed; retry later."

echo "[firstboot] Downloading Piper female voice (en_US-amy-medium)..."
VOICES=/opt/aios/voices
mkdir -p "$VOICES"
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium"
[ -f "$VOICES/en_US-amy-medium.onnx" ] || \
    curl -fsSL -o "$VOICES/en_US-amy-medium.onnx" "$BASE/en_US-amy-medium.onnx" || true
[ -f "$VOICES/en_US-amy-medium.onnx.json" ] || \
    curl -fsSL -o "$VOICES/en_US-amy-medium.onnx.json" "$BASE/en_US-amy-medium.onnx.json" || true
chown -R aios:aios "$VOICES" || true

echo "[firstboot] Restarting AI-OS services..."
systemctl restart aios aios-voice 2>/dev/null || true

touch "$DONE"
echo "[firstboot] Done."
