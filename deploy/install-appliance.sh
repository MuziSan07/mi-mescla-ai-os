#!/usr/bin/env bash
# ============================================================================
#  AI-OS Appliance installer  (Ubuntu Server 22.04/24.04, VM target)
#
#  Turns a fresh Ubuntu Server VM into an "AI-OS appliance": the machine boots
#  straight into a fullscreen dashboard, with the FastAPI backend + Ollama
#  running as services underneath.
#
#  Usage (on the VM, from the repo root):
#      sudo bash deploy/install-appliance.sh
#
#  Idempotent-ish: safe to re-run. Reboot when it finishes.
# ============================================================================
set -euo pipefail

APP_USER="aios"
APP_HOME="/opt/aios"
APP_DIR="${APP_HOME}/app"
VENV_DIR="${APP_HOME}/venv"
DEFAULT_MODEL="${DEFAULT_LOCAL_MODEL:-llama3.2}"
REPO_SRC="$(cd "$(dirname "$0")/.." && pwd)"   # the repo this script lives in

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

if [ "$(id -u)" -ne 0 ]; then
    echo "Please run as root:  sudo bash deploy/install-appliance.sh" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
log "1/8  Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip curl ca-certificates rsync \
    xserver-xorg xinit openbox unclutter \
    ffmpeg espeak-ng libsndfile1 libportaudio2 alsa-utils \
    chromium || apt-get install -y --no-install-recommends chromium-browser || true

# ---------------------------------------------------------------------------
log "2/8  Creating '${APP_USER}' user and copying the app to ${APP_DIR}"
id -u "${APP_USER}" >/dev/null 2>&1 || useradd --create-home --shell /bin/bash "${APP_USER}"
mkdir -p "${APP_DIR}"
# Copy repo into place (exclude venv/git noise).
rsync -a --delete \
    --exclude '.git' --exclude 'venv' --exclude '__pycache__' \
    "${REPO_SRC}/" "${APP_DIR}/"
chown -R "${APP_USER}:${APP_USER}" "${APP_HOME}"

# ---------------------------------------------------------------------------
log "3/8  Creating Python virtualenv and installing AI-OS"
sudo -u "${APP_USER}" python3 -m venv "${VENV_DIR}"
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install --upgrade pip wheel
# Core app (+ optional integrations + voice + wake; drop extras for a lean install).
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install -e "${APP_DIR}[standard,integrations,voice,wake]" \
    || sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install -e "${APP_DIR}"
# Let the appliance user reach the microphone/speaker.
usermod -aG audio "${APP_USER}" || true

# ---------------------------------------------------------------------------
log "4/8  Writing .env (if missing)"
if [ ! -f "${APP_DIR}/.env" ]; then
    cp "${APP_DIR}/deploy/.env.appliance" "${APP_DIR}/.env"
    # Generate a real secret key.
    SECRET="$(head -c 48 /dev/urandom | base64 | tr -d '/+=' | head -c 48)"
    sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET}|" "${APP_DIR}/.env"
    chown "${APP_USER}:${APP_USER}" "${APP_DIR}/.env"
    echo "Wrote ${APP_DIR}/.env  (edit it to add cloud API keys for hybrid mode)"
fi

# ---------------------------------------------------------------------------
log "5/8  Installing Ollama (local model backend) and pulling '${DEFAULT_MODEL}'"
if ! command -v ollama >/dev/null 2>&1; then
    curl -fsSL https://ollama.com/install.sh | sh
fi
systemctl enable --now ollama || true
# Pull the default model (may take a while depending on bandwidth).
sudo -u "${APP_USER}" ollama pull "${DEFAULT_MODEL}" || \
    echo "WARN: could not pull ${DEFAULT_MODEL} now — run 'ollama pull ${DEFAULT_MODEL}' later."

# ---------------------------------------------------------------------------
log "5b/8  Downloading Piper female voice (en_US-amy-medium)"
VOICES_DIR="${APP_HOME}/voices"
mkdir -p "${VOICES_DIR}"
PIPER_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium"
if [ ! -f "${VOICES_DIR}/en_US-amy-medium.onnx" ]; then
    curl -fsSL -o "${VOICES_DIR}/en_US-amy-medium.onnx" \
        "${PIPER_BASE}/en_US-amy-medium.onnx" && \
    curl -fsSL -o "${VOICES_DIR}/en_US-amy-medium.onnx.json" \
        "${PIPER_BASE}/en_US-amy-medium.onnx.json" || \
    echo "WARN: could not download Piper voice — download it later into ${VOICES_DIR}."
fi
chown -R "${APP_USER}:${APP_USER}" "${VOICES_DIR}"
# Point the app at the voices dir + Whisper model.
grep -q '^PIPER_VOICES_DIR=' "${APP_DIR}/.env" || echo "PIPER_VOICES_DIR=${VOICES_DIR}" >> "${APP_DIR}/.env"
grep -q '^WHISPER_MODEL='     "${APP_DIR}/.env" || echo "WHISPER_MODEL=base"          >> "${APP_DIR}/.env"

# ---------------------------------------------------------------------------
log "6/8  Installing the backend + wake-word systemd services"
cp "${APP_DIR}/deploy/aios.service" /etc/systemd/system/aios.service
cp "${APP_DIR}/deploy/aios-voice.service" /etc/systemd/system/aios-voice.service
systemctl daemon-reload
systemctl enable --now aios
# Wake-word daemon needs a microphone; enable it but don't fail the install if
# there's no audio device on this VM (user can start it once a mic is attached).
systemctl enable aios-voice || true
systemctl start aios-voice || echo "NOTE: aios-voice not started (no mic yet?). Start later: systemctl start aios-voice"

# ---------------------------------------------------------------------------
log "7/8  Configuring the kiosk (auto-login + fullscreen dashboard)"
install -o "${APP_USER}" -g "${APP_USER}" -m 0755 \
    "${APP_DIR}/deploy/xinitrc.kiosk" "/home/${APP_USER}/.xinitrc"

# Start X automatically after console login on tty1.
BASH_PROFILE="/home/${APP_USER}/.bash_profile"
if ! grep -q 'startx' "${BASH_PROFILE}" 2>/dev/null; then
    cat >> "${BASH_PROFILE}" <<'EOF'
# Launch the AI-OS kiosk on tty1 login
if [ -z "${DISPLAY}" ] && [ "${XDG_VTNR}" = "1" ]; then
    exec startx
fi
EOF
    chown "${APP_USER}:${APP_USER}" "${BASH_PROFILE}"
fi

# Auto-login the appliance user on tty1.
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/override.conf <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin ${APP_USER} --noclear %I \$TERM
EOF
systemctl daemon-reload

# ---------------------------------------------------------------------------
log "8/8  Done"
cat <<EOF

  AI-OS appliance is installed.

    Backend service : systemctl status aios
    Dashboard URL   : http://localhost:8080/dashboard-ui
    API docs        : http://localhost:8080/docs
    Provider status : http://localhost:8080/api/v1/gateway/providers/status

  Reboot to enter kiosk mode:   sudo reboot

  Hybrid cloud fallback: edit ${APP_DIR}/.env, add OPENAI_API_KEY / ANTHROPIC_API_KEY,
  then:  sudo systemctl restart aios
EOF
