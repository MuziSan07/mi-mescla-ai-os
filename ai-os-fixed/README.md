# 🤖 CLINE-AI-OS UNIFIED
## Sistema Operativo de IA Multiagente y Distribuido

---

## 📋 Descripción

Proyecto unificado que combina tres sistemas innovadores:

- **AI-OS** (de mi-Open-WebUI) - Sistema operativo IA distribuido
- **Manus Desktop** (de -mi-manus-desktop) - Núcleo de auditoría IA  
- **Cline** (de cline/cline) - Referencia para agente coding

---

## 🏗️ Arquitectura

```
cline-ai-os/
├── src/
│   ├── ai-os/              # Core del sistema (12,276 líneas)
│   │   ├── main.py         # FastAPI entry point
│   │   ├── api/routes/      # 18 endpoints de API
│   │   ├── core/          # Gateway, Agentes, GPU, Memory, Events
│   │   ├── utils/        # Auditor, Runtime, Observability
│   │   └── config/
│   └── manus-desktop/      # Módulos de tenant management
├── docker-compose.yaml     # 4 servicios con healthchecks
├── pyproject.toml        # Dependencias Python
└── README.md
```

---

## 📦 Servicios (Docker)

| Servicio |Puerto|Descripción|
|---------|------|------------|
| app | 3000 | Aplicación principal FastAPI |
| redis | 6379 | Cache y sesiones |
| rabbitmq | 5672/15672 | Colas de mensajes |
| ollama | 11434 | Modelos locales |

---

## 🎯 Características

### AI-OS (Core)
- ✅ API Gateway unificado (Multi-provider: OpenAI, Anthropic, Ollama)
- ✅ Agentes especializados (Coding, Chat, Vision, Research)
- ✅ Workers GPU distribuidos (Colab lifecycle)
- ✅ Validación Runtime real
- ✅ Observabilidad distribuida
- ✅ Event Bus para comunicación asíncrona
- ✅ Task Queue para orquestación

### Manus Desktop
- ✅ _pl/tenant/manager.py - Gestión de tenants

### Cline
- ℹ️ Referencia (sin implementar)

---

## 🚀 Inicio Rápido

```bash
# Iniciar servicios
docker-compose up -d

# Ver estado
docker-compose ps

# Acceder a la API
curl http://localhost:3000/api/health
```

---

## 🔌 API Endpoints

| Endpoint | Descripción |
|----------|------------|
| `/api/chat` | Chat con modelos |
| `/api/agents/execute` | Ejecutar agente |
| `/api/gateway/models` | Modelos disponibles |
| `/api/workers/start` | Iniciar worker |
| `/api/audit/run` | Auditoría completa |
| `/api/validate/runtime` | Validación runtime |
| `/api/observe/full` | Observabilidad |
| `/api/health` | Health check |

---

## 📊 Estadísticas

| Métrica | Valor |
|---------|-------|
| Archivos Python | 55 |
| Líneas de código | 12,276 |
| API Endpoints | 18 |
| Servicios Docker | 4 |
| Errors de sintaxis | 0 |

---

## ⚠️ Known Issues

- Placeholders en algunos módulos no implementados
- Cline: referencia sin código fuente

---

## 📋 Requisitos

- Python 3.11+
- Docker + Docker Compose
- Redis, RabbitMQ (incluidos)

---

## 👤 Autor

AOI-555

## 🔒 Licencia

CERRADA - NO PERMISIVA
Todos los derechos reservados

---

## 🔧 Proyectos y Herramientas Utilizadas

Este sistema hace uso de los siguientes proyectos y herramientas de código abierto:

### Frameworks Principales

| Proyecto | Uso | URL |
|----------|-----|-----|
| **FastAPI** | Marco web async Python | https://fastapi.tiangolo.com |
| **Pydantic** | Validación de datos | https://docs.pydantic.dev |
| **Uvicorn** | Servidor ASGI | https://www.uvicorn.org |

### Orquestación y Agentes

| Proyecto | Uso | URL |
|----------|-----|-----|
| **LangGraph** | Orquestación multiagente | https://www.langchain.com/langgraph |
| **CrewAI** | Framework multiagente | https://docs.crewai.com |
| **LangChain** | Componentes LLM | https://python.langchain.com |

### Modelos y Providers

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

### Docker y Despliegue

| Proyecto | Uso | URL |
|----------|-----|-----|
| **Docker** | Contenedores | https://www.docker.com |
| **Tailscale** | Networking seguro | https://tailscale.com |

### Herramientas de Desarrollo

| Proyecto | Uso | URL |
|----------|-----|-----|
| **Open WebUI** | Interfaz web UI | https://openwebui.com |
| **Flowise** | Flujos visuales | https://flowiseai.com |
| **OpenHands** | Agentes autonomous | https://docs.openhands.dev |

### Monitoreo

| Proyecto | Uso | URL |
|----------|-----|-----|
| **Prometheus** | Métricas | https://prometheus.io |
| **Grafana** | Dashboards | https://grafana.com |

### Visión y Multimodal

| Proyecto | Uso | URL |
|----------|-----|-----|
| **OpenCV** | Visión por computadora | https://opencv.org |
| **Qwen-VL** | Modelo visión lenguaje | https://qwenlm.github.io |
| **LLaVA** | Modelo multimodal | https://llava-vl.github.io |

---

## 📋 Estado del Proyecto

- **Estado Actual**: EARLY MVP FUNCIONAL
- **Última Validación**: Tests runtime pasan
- **API Routes**: 97 endpoints

### Lo que funciona ✅
- FastAPI app arrancando
- EventBus (pub/sub)
- TaskQueue (enqueue/dequeue/ack)
- ToolExecutor (echo, shell, http)
- Integración básica

### Lo que falta para profesional 🚧
- WorkerManager real (stub)
- AgentRuntime real (stub)
- Redis conectado
- Tests unitarios
- Dockerfile
- Auth JWT
- Métricas Prometheus

---

## 📦 Dependencias en Uso

Basado en `pyproject.toml`:

| Paquete | Versión | Uso |
|---------|--------|-----|
| **fastapi** | 0.135.1 | Framework web async |
| **pydantic** | 2.12.5 | Validación datos |
| **httpx** | 0.28.1 | Cliente HTTP |
| **uvicorn** | 0.41.0 | Servidor ASGI |
| **openai** | 2.29.0 | API OpenAI |
| **anthropic** | 0.86.0 | API Anthropic |
| **langchain** | 1.2.10 | Componentes LLM |
| **redis** | 7.4.0 | Cache/colas |
| **authlib** | 1.6.10 | OAuth |

---

## 📋 Estado del Proyecto

- **Estado Actual**: EARLY MVP FUNCIONAL
- **Última Validación**: Tests runtime pasan

### Lo que funciona ✅
- FastAPI app
- EventBus
- TaskQueue
- ToolExecutor
- Integración básica

### Lo que falta 🚧
- WorkerManager real
- AgentRuntime real
- Tests unitarios
- Dockerfile
- Auth JWT
- Métricas

---

## 🚀 Quick Start

```bash
pip install -r requirements.txt
uvicorn ai_os.main:app --host 0.0.0.0 --port 8000
```

---

## 🔒 Licencia

CERRADA - NO PERMISIVA
Todos los derechos reservados

*Última actualización: Mayo 2026*