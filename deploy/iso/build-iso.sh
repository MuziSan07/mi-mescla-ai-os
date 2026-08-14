#!/usr/bin/env bash
# ============================================================================
#  Build AI-OS.iso  — a bootable Debian live image that boots straight into the
#  AI-OS voice assistant.
#
#  RUN ON A DEBIAN/UBUNTU HOST (amd64) with sudo and ~15 GB free disk:
#      sudo bash deploy/iso/build-iso.sh
#
#  Output: ai-os-amd64.iso in the repo root.
#
#  The image contains the app + all services + kiosk. Ollama model and the Piper
#  voice are fetched on FIRST BOOT (keeps the ISO ~2-3 GB instead of 6 GB+).
# ============================================================================
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD="${BUILD_DIR:-/tmp/aios-iso-build}"
DIST="${DEBIAN_DIST:-bookworm}"

if [ "$(id -u)" -ne 0 ]; then
    echo "Please run as root:  sudo bash deploy/iso/build-iso.sh" >&2
    exit 1
fi

echo "==> Ensuring live-build is installed"
command -v lb >/dev/null 2>&1 || { apt-get update && apt-get install -y live-build rsync; }

echo "==> Preparing build tree at ${BUILD}"
rm -rf "${BUILD}"
mkdir -p "${BUILD}"
cd "${BUILD}"

echo "==> lb config (${DIST}, amd64)"
lb config \
    --distribution "${DIST}" \
    --architectures amd64 \
    --debian-installer none \
    --archive-areas "main contrib non-free non-free-firmware" \
    --bootappend-live "boot=live components quiet splash"

echo "==> Adding package list"
mkdir -p config/package-lists
cp "${REPO}/deploy/iso/aios.list.chroot" config/package-lists/aios.list.chroot

echo "==> Adding provisioning hook"
mkdir -p config/hooks/normal
cp "${REPO}/deploy/iso/aios.hook.chroot" config/hooks/normal/0100-aios.hook.chroot
chmod +x config/hooks/normal/0100-aios.hook.chroot

echo "==> Baking the AI-OS repo into the image (/opt/aios/app)"
mkdir -p config/includes.chroot/opt/aios/app
rsync -a \
    --exclude '.git' --exclude 'venv' --exclude '__pycache__' \
    --exclude 'workspace' --exclude 'vault' --exclude 'voices' \
    --exclude '*.iso' \
    "${REPO}/" config/includes.chroot/opt/aios/app/

echo "==> Building the ISO (this takes a while)..."
lb build

ISO_OUT="$(ls -1 *.iso 2>/dev/null | head -1 || true)"
if [ -n "${ISO_OUT}" ]; then
    mv "${ISO_OUT}" "${REPO}/ai-os-amd64.iso"
    echo ""
    echo "==> Built: ${REPO}/ai-os-amd64.iso"
    echo "    Boot it in a VM (enable a mic in the hypervisor for hands-free voice)."
    echo "    First boot fetches the model + voice, then it lands in the dashboard."
else
    echo "ERROR: no .iso produced — check the lb build output above." >&2
    exit 1
fi
