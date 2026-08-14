# AI-OS as a Bootable Appliance (VM)

Turn the AI-OS project into a machine that **boots straight into the AI-OS
dashboard** — no desktop, no login screen. Linux runs underneath as invisible
plumbing (like a router or a NAS); the user just sees AI-OS.

This is the **Phase 1 "kiosk appliance"** target: VM-only, hybrid AI backend
(local Ollama + optional cloud fallback).

---

## What you get

```
  Power on VM
      │
      ▼
  Ubuntu boots (headless, auto-login on tty1)
      │
      ├─ ollama.service      →  local models
      ├─ aios.service        →  FastAPI backend + dashboard  (port 8080)
      └─ kiosk X session     →  Chromium fullscreen → /dashboard-ui
```

No Linux desktop is ever shown. The browser is locked to the AI-OS dashboard.

---

## Prerequisites

- A VM (VirtualBox, VMware, Proxmox, or a cloud VM) with:
  - **Ubuntu Server 22.04 or 24.04** freshly installed
  - **≥ 4 GB RAM** (8 GB+ recommended if running local models)
  - **≥ 20 GB disk** (local models are multi-GB)
  - Internet access for the first install
- The AI-OS repo copied onto the VM.

> Local LLMs are heavy. On a small VM, either use a tiny model
> (`DEFAULT_LOCAL_MODEL=llama3.2:1b`) or run **cloud-only** by adding an API key
> and skipping the model pull.

---

## Install (one command)

Copy the repo to the VM, then from the repo root:

```bash
sudo bash deploy/install-appliance.sh
```

The script:
1. Installs system packages (Python, Xorg, Openbox, Chromium).
2. Creates an `aios` user and copies the app to `/opt/aios/app`.
3. Builds a virtualenv and installs AI-OS (`pip install -e .`).
4. Writes `.env` from `deploy/.env.appliance` with a generated `SECRET_KEY`.
5. Installs **Ollama** and pulls the default model (`llama3.2`).
6. Installs and enables the **`aios`** backend service.
7. Configures **auto-login + kiosk** (Chromium fullscreen on the dashboard).

Then:

```bash
sudo reboot
```

The VM comes back up inside the AI-OS dashboard.

---

## Hybrid backend (local + cloud)

By default the appliance runs **local-only** via Ollama. To enable cloud
fallback, edit `/opt/aios/app/.env`:

```bash
OPENAI_API_KEY=sk-...          # any one (or more) of these
ANTHROPIC_API_KEY=sk-ant-...
```

then restart the backend:

```bash
sudo systemctl restart aios
```

Check what's active:

```bash
curl http://localhost:8080/api/v1/gateway/providers/status
# -> {"mode": "hybrid", "usable": ["openai","ollama","local"], ...}
```

Routing logic: the gateway tries the requested model, walks a fallback chain,
**skips providers with no credentials**, and always ends at local Ollama — so
the box works offline and gets smarter when keys are present.

---

## Managing the appliance

| Action | Command |
|---|---|
| Backend status / logs | `systemctl status aios` · `journalctl -u aios -f` |
| Restart backend | `sudo systemctl restart aios` |
| Pull another model | `sudo -u aios ollama pull mistral` |
| Exit kiosk (debug) | switch VT: `Ctrl+Alt+F2`, log in |
| Dashboard (from host) | `http://<vm-ip>:8080/dashboard-ui` |
| Setup wizard (optional keys) | `http://<vm-ip>:8080/setup-ui` |
| Voice page (push-to-talk) | `http://<vm-ip>:8080/voice-ui` |
| Wake-word daemon status | `systemctl status aios-voice` · `journalctl -u aios-voice -f` |
| API docs | `http://<vm-ip>:8080/docs` |

---

## Voice (Phase 2)

Two ways to talk to it — both fully local and free:

**Push-to-talk (browser):** open `/voice-ui`, tap the mic, speak. She transcribes
with Whisper, thinks with your local model, and replies in a Piper female voice.

**Hands-free (wake word):** the `aios-voice` daemon listens on the appliance's
microphone for a wake word (default **"Hey Jarvis"**), then records your command
and answers out loud — no clicking. Configure in `.env`:

```bash
WAKE_WORD=hey_jarvis      # built-ins: hey_jarvis, alexa, hey_mycroft
WAKE_THRESHOLD=0.5
```

```bash
sudo systemctl restart aios-voice     # after changing the wake word
```

> A custom **"Hey &lt;Name&gt;"** wake word requires training an openWakeWord model
> (see the openWakeWord training notebook). The built-ins work out of the box.
> The daemon needs a microphone attached to the VM (enable a mic in your
> hypervisor's audio settings).

---

## Alternative: docker-compose (no kiosk)

If you just want the services (not the boot-into-dashboard experience), the
repo ships `docker-compose.yaml` (app + Redis + RabbitMQ + Ollama):

```bash
docker compose up -d
# dashboard at http://localhost:8080/dashboard-ui
```

---

## Roadmap

- **Phase 0 — Fix the app** ✅ (boots, hybrid routing, clean API, dashboard wired)
- **Phase 1 — Kiosk appliance** ← *you are here*
- **Phase 2 — Distributable `AI-OS.iso`** (build with `debian-live-build` /
  Buildroot so it boots on any VM or USB stick)
- **Phase 3 — C++ hot-path engine** (only where profiling shows a bottleneck)

See the conversation notes for details on each phase.
