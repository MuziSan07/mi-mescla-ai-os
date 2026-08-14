# Building AI-OS.iso — a bootable AI operating system

This kit turns the whole AI-OS appliance into a single **bootable ISO** you can
run on any VM or USB stick. It's the Phase 7 deliverable: the distributable image.

Boot it and the machine comes up **inside the AI-OS voice assistant** — Linux is
invisible underneath.

---

## What's in the image

- Debian (live) + the AI-OS app installed at `/opt/aios`
- Services enabled: `aios` (API + dashboard), `aios-voice` (wake word), Ollama
- Kiosk auto-login → Chromium fullscreen on the dashboard
- Everything to run **fully local + free**

Kept *out* of the ISO (fetched on first boot, to keep it small):
- The Ollama model (`llama3.2`)
- The Piper female voice (`en_US-amy-medium`)

---

## Build it (on a Debian/Ubuntu host)

You need an **amd64 Debian or Ubuntu** machine (or VM) with `sudo` and ~15 GB free.
This cannot be built on Windows/macOS directly — use a Linux VM if needed.

```bash
sudo bash deploy/iso/build-iso.sh
```

It installs `live-build`, assembles the image (app + services + kiosk baked in),
and produces **`ai-os-amd64.iso`** in the repo root. The build takes a while and
downloads a few hundred MB of packages.

Options:
```bash
DEBIAN_DIST=bookworm BUILD_DIR=/tmp/aios-iso-build sudo -E bash deploy/iso/build-iso.sh
```

---

## Boot it

1. Create a VM (VirtualBox/VMware/Proxmox), attach `ai-os-amd64.iso` as the boot disk.
2. Give it **≥ 4 GB RAM** (8 GB+ for comfortable local models) and **enable audio /
   a microphone** in the hypervisor if you want hands-free voice.
3. Boot. On **first boot** it fetches the model + voice (needs internet), then drops
   into the AI-OS dashboard. Subsequent boots are instant.

From your host you can also reach it at `http://<vm-ip>:8080/dashboard-ui`,
`/voice-ui`, and `/setup-ui`.

---

## First-boot provisioning

`aios-firstboot.service` runs once ([deploy/firstboot.sh](../firstboot.sh)):
installs Ollama, pulls the default model, downloads the Piper voice, then marks
itself done (`/opt/aios/.firstboot-done`) so it never runs again.

Watch it:
```bash
journalctl -u aios-firstboot -f
```

---

## Notes & honesty

- This kit is **assembled and syntax-checked but not built end-to-end here**
  (building an ISO needs a Linux host + root + time). Run it on Debian/Ubuntu; if
  `lb build` errors, paste the output and it can be fixed.
- To make a **fully-offline ISO** (no first-boot download), pre-place the model and
  voice into `config/includes.chroot/` before `lb build` — at the cost of a much
  larger image.
- For a persistent install (not live), add the Debian installer or use the appliance
  installer ([../install-appliance.sh](../install-appliance.sh)) on a normal Debian VM.
