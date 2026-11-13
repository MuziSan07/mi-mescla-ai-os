# CLINE-AI-OS UNIFIED

## Multi-agent, distributed AI operating system

A unified project that combines three systems:

- **AI-OS** (from mi-Open-WebUI) — distributed AI operating system
- **Manus Desktop** (from mi-manus-desktop) — AI audit core
- **Cline** (from cline/cline) — reference for the coding agent

---

## Architecture

```
cline-ai-os/
├── src/
│   ├── ai_os/               # System core
│   │   ├── main.py          # FastAPI entry point
│   │   ├── api/routes/      # API endpoints
│   │   ├── core/            # Gateway, agents, GPU, memory, events, voice
│   │   ├── utils/           # Auditor, runtime, observability
│   │   └── config/
│   └── manus-desktop/       # Tenant-management modules
├── deploy/                  # Appliance and bootable-ISO build kits
├── native/                  # Optional C++ tokenizer accelerator
├── docker-compose.yaml      # Services with healthchecks
├── pyproject.toml           # Python dependencies
└── README.md
```

---

## Services (Docker)

| Service | Port | Description |
|---------|------|-------------|
| app | 3000 | Main FastAPI application |
| redis | 6379 | Cache and sessions |
| rabbitmq | 5672 / 15672 | Message queues |
| ollama | 11434 | Local models |

---

## Features

### AI-OS (core)

- Unified API gateway (multi-provider: OpenAI, Anthropic, Ollama)
- Specialized agents (coding, chat, vision, research)
- Distributed GPU workers (Colab lifecycle)
- Real runtime validation
- Distributed observability
- Event Bus for asynchronous communication
- Task Queue for orchestration

### Manus Desktop

- `_pl/tenant/manager.py` — tenant management

### Cline

- Reference (not yet implemented)

---

## Quick start

### With Docker

```bash
# Start services
docker-compose up -d

# Check status
docker-compose ps

# Hit the API
curl http://localhost:3000/api/health
```

### Locally

```bash
pip install -e .
uvicorn ai_os.main:app --host 0.0.0.0 --port 8000
```

---

## API endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/chat` | Chat with models |
| `/api/agents/execute` | Run an agent |
| `/api/gateway/models` | Available models |
| `/api/workers/start` | Start a worker |
| `/api/audit/run` | Full audit |
| `/api/validate/runtime` | Runtime validation |
| `/api/observe/full` | Observability |
| `/api/health` | Health check |

---

## Project status

- **Current status:** early functional MVP
- **Last validation:** runtime tests pass

### Implemented

- FastAPI app boots
- Event Bus (pub/sub)
- Task Queue (enqueue / dequeue / ack)
- Tool Executor (echo, shell, http)
- Basic integration

### Pending

- Real WorkerManager (currently a stub)
- Real AgentRuntime (currently a stub)
- Redis connected
- Expanded unit tests
- JWT authentication
- Prometheus metrics

---

## Statistics

| Metric | Value |
|--------|-------|
| Python files | 55 |
| Lines of code | 12,276 |
| API endpoints | 18 |
| Docker services | 4 |
| Syntax errors | 0 |

---

## Dependencies in use

Based on `pyproject.toml`:

| Package | Version | Use |
|---------|---------|-----|
| **fastapi** | 0.135.1 | Async web framework |
| **pydantic** | 2.12.5 | Data validation |
| **httpx** | 0.28.1 | HTTP client |
| **uvicorn** | 0.41.0 | ASGI server |
| **openai** | 2.29.0 | OpenAI API |
| **anthropic** | 0.86.0 | Anthropic API |
| **langchain** | 1.2.10 | LLM components |
| **redis** | 7.4.0 | Cache / queues |
| **authlib** | 1.6.10 | OAuth |

---

## Requirements

- Python 3.11+
- Docker + Docker Compose
- Redis, RabbitMQ (included in the compose file)

---

## Projects and tools used

This system makes use of the following open-source projects and tools.

### Core frameworks

| Project | Use | URL |
|---------|-----|-----|
| **FastAPI** | Async Python web framework | https://fastapi.tiangolo.com |
| **Pydantic** | Data validation | https://docs.pydantic.dev |
| **Uvicorn** | ASGI server | https://www.uvicorn.org |

### Orchestration and agents

| Project | Use | URL |
|---------|-----|-----|
| **LangGraph** | Multi-agent orchestration | https://www.langchain.com/langgraph |
| **CrewAI** | Multi-agent framework | https://docs.crewai.com |
| **LangChain** | LLM components | https://python.langchain.com |

### Models and providers

| Project | Use | URL |
|---------|-----|-----|
| **LiteLLM** | LLM unification | https://docs.litellm.ai |
| **Ollama** | Local models | https://ollama.com |
| **OpenAI** | OpenAI API | https://platform.openai.com |
| **Anthropic** | Claude API | https://www.anthropic.com |

### Infrastructure

| Project | Use | URL |
|---------|-----|-----|
| **Ray** | Distributed computing | https://www.ray.io |
| **Redis** | Cache and queues | https://redis.io |
| **RabbitMQ** | Message broker | https://www.rabbitmq.com |

### Docker and deployment

| Project | Use | URL |
|---------|-----|-----|
| **Docker** | Containers | https://www.docker.com |
| **Tailscale** | Secure networking | https://tailscale.com |

### Development tools

| Project | Use | URL |
|---------|-----|-----|
| **Open WebUI** | Web interface | https://openwebui.com |
| **Flowise** | Visual flows | https://flowiseai.com |
| **OpenHands** | Autonomous agents | https://docs.openhands.dev |

### Monitoring

| Project | Use | URL |
|---------|-----|-----|
| **Prometheus** | Metrics | https://prometheus.io |
| **Grafana** | Dashboards | https://grafana.com |

### Vision and multimodal

| Project | Use | URL |
|---------|-----|-----|
| **OpenCV** | Computer vision | https://opencv.org |
| **Qwen-VL** | Vision-language model | https://qwenlm.github.io |
| **LLaVA** | Multimodal model | https://llava-vl.github.io |

---

## Author

Ali Basit

## License

Released under the MIT License. See the [LICENSE](LICENSE) file for details.

---

*Last updated: 2026*
