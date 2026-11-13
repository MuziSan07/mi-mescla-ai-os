# CLINE-AI-OS UNIFIED

## Sistema operativo de IA multiagente y distribuido

Proyecto unificado que combina tres sistemas:

- **AI-OS** (de mi-Open-WebUI) — sistema operativo de IA distribuido
- **Manus Desktop** (de mi-manus-desktop) — núcleo de auditoría de IA
- **Cline** (de cline/cline) — referencia para el agente de coding

---

## Arquitectura

```
cline-ai-os/
├── src/
│   ├── ai_os/               # Núcleo del sistema
│   │   ├── main.py          # Punto de entrada FastAPI
│   │   ├── api/routes/      # Endpoints de la API
│   │   ├── core/            # Gateway, agentes, GPU, memoria, eventos, voz
│   │   ├── utils/           # Auditor, runtime, observabilidad
│   │   └── config/
│   └── manus-desktop/       # Módulos de gestión de tenants
├── deploy/                  # Appliance y kits de ISO booteable
├── native/                  # Acelerador opcional de tokenizer (C++)
├── docker-compose.yaml      # Servicios con healthchecks
├── pyproject.toml           # Dependencias Python
└── README.md
```

---

## Servicios (Docker)

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| app | 3000 | Aplicación principal FastAPI |
| redis | 6379 | Cache y sesiones |
| rabbitmq | 5672 / 15672 | Colas de mensajes |
| ollama | 11434 | Modelos locales |

---

## Características

### AI-OS (núcleo)

- API Gateway unificado (multi-provider: OpenAI, Anthropic, Ollama)
- Agentes especializados (coding, chat, visión, research)
- Workers GPU distribuidos (Colab lifecycle)
- Validación runtime real
- Observabilidad distribuida
- Event Bus para comunicación asíncrona
- Task Queue para orquestación

### Manus Desktop

- `_pl/tenant/manager.py` — gestión de tenants

### Cline

- Referencia (sin implementar)

---

## Inicio rápido

### Con Docker

```bash
# Iniciar servicios
docker-compose up -d

# Ver estado
docker-compose ps

# Acceder a la API
curl http://localhost:3000/api/health
```

### En local

```bash
pip install -e .
uvicorn ai_os.main:app --host 0.0.0.0 --port 8000
```

---

## Endpoints de la API

| Endpoint | Descripción |
|----------|-------------|
| `/api/chat` | Chat con modelos |
| `/api/agents/execute` | Ejecutar agente |
| `/api/gateway/models` | Modelos disponibles |
| `/api/workers/start` | Iniciar worker |
| `/api/audit/run` | Auditoría completa |
| `/api/validate/runtime` | Validación runtime |
| `/api/observe/full` | Observabilidad |
| `/api/health` | Health check |

---

## Estado del proyecto

- **Estado actual:** MVP funcional temprano
- **Última validación:** los tests de runtime pasan

### Implementado

- Arranque de la app FastAPI
- Event Bus (pub/sub)
- Task Queue (enqueue / dequeue / ack)
- Tool Executor (echo, shell, http)
- Integración básica

### Pendiente

- WorkerManager real (actualmente stub)
- AgentRuntime real (actualmente stub)
- Redis conectado
- Tests unitarios ampliados
- Autenticación JWT
- Métricas Prometheus

---

## Estadísticas

| Métrica | Valor |
|---------|-------|
| Archivos Python | 55 |
| Líneas de código | 12,276 |
| Endpoints de la API | 18 |
| Servicios Docker | 4 |
| Errores de sintaxis | 0 |

---

## Dependencias en uso

Basado en `pyproject.toml`:

| Paquete | Versión | Uso |
|---------|---------|-----|
| **fastapi** | 0.135.1 | Framework web async |
| **pydantic** | 2.12.5 | Validación de datos |
| **httpx** | 0.28.1 | Cliente HTTP |
| **uvicorn** | 0.41.0 | Servidor ASGI |
| **openai** | 2.29.0 | API OpenAI |
| **anthropic** | 0.86.0 | API Anthropic |
| **langchain** | 1.2.10 | Componentes LLM |
| **redis** | 7.4.0 | Cache / colas |
| **authlib** | 1.6.10 | OAuth |

---

## Requisitos

- Python 3.11+
- Docker + Docker Compose
- Redis, RabbitMQ (incluidos en el compose)

---

## Proyectos y herramientas utilizadas

Este sistema hace uso de los siguientes proyectos y herramientas de código abierto.

### Frameworks principales

| Proyecto | Uso | URL |
|----------|-----|-----|
| **FastAPI** | Marco web async Python | https://fastapi.tiangolo.com |
| **Pydantic** | Validación de datos | https://docs.pydantic.dev |
| **Uvicorn** | Servidor ASGI | https://www.uvicorn.org |

### Orquestación y agentes

| Proyecto | Uso | URL |
|----------|-----|-----|
| **LangGraph** | Orquestación multiagente | https://www.langchain.com/langgraph |
| **CrewAI** | Framework multiagente | https://docs.crewai.com |
| **LangChain** | Componentes LLM | https://python.langchain.com |

### Modelos y providers

| Proyecto | Uso | URL |
|----------|-----|-----|
| **LiteLLM** | Unificación de LLMs | https://docs.litellm.ai |
| **Ollama** | Modelos locales | https://ollama.com |
| **OpenAI** | API OpenAI | https://platform.openai.com |
| **Anthropic** | Claude API | https://www.anthropic.com |

### Infraestructura

| Proyecto | Uso | URL |
|----------|-----|-----|
| **Ray** | Computación distribuida | https://www.ray.io |
| **Redis** | Cache y colas | https://redis.io |
| **RabbitMQ** | Broker de mensajes | https://www.rabbitmq.com |

### Docker y despliegue

| Proyecto | Uso | URL |
|----------|-----|-----|
| **Docker** | Contenedores | https://www.docker.com |
| **Tailscale** | Networking seguro | https://tailscale.com |

### Herramientas de desarrollo

| Proyecto | Uso | URL |
|----------|-----|-----|
| **Open WebUI** | Interfaz web | https://openwebui.com |
| **Flowise** | Flujos visuales | https://flowiseai.com |
| **OpenHands** | Agentes autónomos | https://docs.openhands.dev |

### Monitoreo

| Proyecto | Uso | URL |
|----------|-----|-----|
| **Prometheus** | Métricas | https://prometheus.io |
| **Grafana** | Dashboards | https://grafana.com |

### Visión y multimodal

| Proyecto | Uso | URL |
|----------|-----|-----|
| **OpenCV** | Visión por computadora | https://opencv.org |
| **Qwen-VL** | Modelo visión-lenguaje | https://qwenlm.github.io |
| **LLaVA** | Modelo multimodal | https://llava-vl.github.io |

---

## Autor

Ali Basit

## Licencia

Publicado bajo la licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.

---

*Última actualización: 2026*
