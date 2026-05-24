# EXECUTION SEMANTICS - Definición Formal

## 1. TASK LIFECYCLE

```
┌─────────────────────────────────────────────────────────────────┐
│                     TASK LIFECYCLE                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CREATED ──→ QUEUED ──→ ASSIGNED ──→ RUNNING ──→ COMPLETED       │
│     │                              │              │                 │
│     │                              │              └─────┬──→ FAILED
│     │                              │                    │             │
│     │                              └─────┬──→ RETRYING ←─→ ERROR
│     │                              │        │                    │
│     └─────────────────────────→ CANCELLED                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Estados y Transiciones

| Estado | Significado | Transiciones válidas |
|--------|------------|---------------------|
| CREATED | Task creado, no en queue | QUEUED, CANCELLED |
| QUEUED | En queue esperando | ASSIGNED, CANCELLED |
| ASSIGNED | Worker tiene task | RUNNING |
| RUNNING | Ejecutando | COMPLETED, FAILED, TIMEOUT |
| RETRYING | Esperando retry | ASSIGNED, MAX_RETRIES |
| COMPLETED | Éxito | Terminal |
| FAILED | Fallo permanente | Terminal |
| CANCELLED | Cancelado por usuario | Terminal |
| TIMEOUT | Excedió tiempo | Terminal |

### Owner del Task

| Operación | Owner | Notas |
|-----------|-------|-------|
| Crear | Caller | Usuario/API |
| Enqueue | TaskQueue | Auto en crear |
| Asignar | WorkerManager | |
| Ejecutar | Worker | |
| Completar | Worker | |
| Cancelar | Caller | Requiere task_id |
| Retry | TaskQueue | Exponential backoff |

---

## 2. WORKER LIFECYCLE

```
STARTING ──→ HEALTHY ──→ BUSY ──→ COMPLETING ──→ HEALTHY
    │           │         │              │
    │           └────┬────┘              │
    │                ↓                  ↓
  FAILED ──→ RECOVERING ──→ RECOVERED ──→ HEALTHY
    │                              │
    └──→ DEAD (after 3 failures) ──────┘
```

### Heartbeat Protocol

```python
# Worker reporta cada 10 segundos
# Si miss 3 heartbeats = UNHEALTHY
# Si miss 5 heartbeats + ASSIGNED = DISCONNECTED
# Tareas reassignadas automáticamente
```

---

## 3. CONCURRENCY MODEL

### Task Queue Concurrency

```python
# Límites configurables
MAX_CONCURRENT_TASKS = 100        # Por worker
MAX_QUEUE_DEPTH = 10000            # Global
BACKPRESSURE_THRESHOLD = 8000    # Empezar rejection
DEAD_LETTER_QUEUE = 1000          # Errores acumulados
```

### Async Semantics

```python
# Cada task corre en su propio asyncio.Task
# Aislamiento por Task
# Cancellation propaga con Task.cancel()
# Timeout usa asyncio.wait_for()
```

### Backpressure Strategy

```
1. Queue < BACKPRESSURE_THRESHOLD
   → Aceptar normal

2. BACKPRESSURE_THRESHOLD < Queue < MAX_QUEUE_DEPTH
   → Aumentar latency gracefully

3. Queue >= MAX_QUEUE_DEPTH
   → 503 Service Unavailable + retry-after
```

---

## 4. FAILURE MODEL

### Failure Types

| Type | Detection | Acción | Recovery |
|------|----------|--------|----------|
| Worker muerte | 3 missed heartbeats | Reassign task | Automático |
| Tool timeout | timeout > MAX_TOOL_TIME | Kill tool | Retry con backoff |
| Provider timeout | timeout > 60s | Retry | Manual intervention |
| Redis caída | Connection error | Fail fast | Circuit breaker |
| Loop infinito | MAX_STEPS exceeded | Kill agent | Log + alert |
| Memory exceed | OOM detected | Kill | Terminate agent |

### Retry Strategy

```python
# Exponential backoff
retry_delays = [1, 2, 4, 8, 16]  # segundos

# Maximum retries: 3
# Retry solo para transient errors
# Permament errors: no retry (404, auth fail)
```

### Circuit Breaker

```python
FAILURE_THRESHOLD = 5      # Errores en ventana
RECOVERY_TIMEOUT = 60s   # Tiempo para recovery  
HALF_OPEN_ATTEMPTS = 3   # Pruebas en half-open
```

---

## 5. AGENT LIFECYCLE

```
SPAWNED ──→ INITIALIZING ──→ EXECUTING ──→ WAITING ──→ TERMINATED
    │                  │            │            │
    │                  │            └───────────→ ERROR
    │                  └──────────────────────→ PAUSED
    │                                          
    └──────────────────────────────────────→ CANCELLED
```

### Ownership

| Operación | Owner |
|-----------|-------|
| Spawn | AgentRuntime |
| Init tools | AgentRuntime |
| Execute step | AgentRuntime |
| Tool selection | AgentDecision |
| Pause | Controller |
| Terminate | Controller (timeout/user) |

---

## 6. STREAMING MODEL

### Event Types

| Event | Producer | Consumer | Format |
|-------|----------|----------|--------|
| TOKEN | ModelProvider | Frontend | SSE |
| LOG | ToolExecutor | Frontend | websocket |
| PROGRESS | AgentRuntime | Frontend | websocket |
| STATUS | TaskQueue | Frontend | websocket |
| TELEMETRY | Worker | Metrics | UDP |

### Correlation

```
correlation_id = UUID
task_id = UUID  
execution_id = UUID
agent_id = UUID

# Todos los eventos incluyen correlation_id
# Permite trace distribuido
```

---

## 7. TOOL EXECUTION MODEL

### Sandbox

```python
# Tool execution sandbox
SANDBOX_TYPE = "gvisor"        # gVisor isolation
MEMORY_LIMIT = 512MB
CPU_LIMIT = 2 cores
NETWORK = "none"               # o whitelist
FILESPACE = 100MB
FILESYSTEM_RO = false          # Read-write tmp
```

### Execution

```python
# Timeout por tool
TERMINAL_TIMEOUT = 30s
BROWSER_TIMEOUT = 120s
FILE_OP_TIMEOUT = 10s

# Resources se liberan después de cada tool
# Cleanup automático con context manager
```

### Tool Categories

| Category | Isolation | Network | Filesystem |
|----------|-----------|--------|-----------|
| READ | Full | Yes | RO |
| WRITE | Full | No | RW(/tmp) |
| TERMINAL | Restricted | No | RW |
| BROWSER | Restricted | Limited | No |

---

## 8. STATE MODEL

### State Classification

| State | Type | Storage | TTL | Replay |
|-------|------|--------|-----|--------|
| Task input | Persistent | DB | 7d | Yes |
| Task output | Persistent | DB | 30d | Yes |
| Task logs | Cached | Redis | 24h | No |
| Agent context | Ephemeral | Memory | 1h | No |
| Session | Persistent | Redis | 24h | Yes |
| Worker metrics | Cached | Memory | 5m | No |
| Events | Transient | EventBus | 0 | No |

### Persistence Strategy

```python
# Checkpointing cada 10 steps
CHECKPOINT_INTERVAL = 10

# Recovery desde checkpoint
# Si agent falla, restart desde último checkpoint
# + replay de events hasta checkpoint
```

---

## 9. OBSERVABILITY MODEL

### Tracing

```
# Trace distribuido con OpenTelemetry
# cada operación tiene trace_id
# Spans por operación mayor

Span Hierarchy:
└── Request
    ├── Orchestration
    │   └── AgentExecution
    │       └── ToolExecution
    │           └── SubTool (optional)
    ├── ModelCall
    └── Persistence
```

### Metrics

| Metric | Type | Labels |
|-------|------|--------|
| task.duration | Histogram | task_type, status |
| queue.depth | Gauge | queue_name |
| worker.tasks | Gauge | worker_id, status |
| agent.steps | Counter | agent_type, outcome |
| model.latency | Histogram | provider, model |

### Structured Logs

```python
# Formato: JSON estructurado
{
  "timestamp": "ISO8601",
  "level": "INFO",
  "trace_id": "uuid",
  "task_id": "uuid",
  "operation": "tool.execution",
  "duration_ms": 123,
  "message": "...",
  "context": {}
}
```

---

## 10. ORCHESTRATION MODEL

### Single Agent Execution

```
user_request
 → create_task(task_type="agent", input=...)
   → enqueue(task)
   → task_queue picks up task
   → spawn_agent(config)
   → execute_agent(agent_id, input)
     → step loop until done or timeout
   → emit events (stream)
   → emit result
   → terminate_agent
```

### Multi-Agent Coordination

```
# Sequential delegation
Agent A ──→ Agent B ──→ Agent C

# Parallel execution  
Agent A ─┬─→ Agent B
          └─→ Agent C

# Hierarchical
Orchestrator ─┬─→ Worker Agent 1
              ├─→ Worker Agent 2
              └─→ Worker Agent 3
```

### Event Flow

```
AgentRuntime publishes:
- agent.started
- agent.step.completed  
- agent.waiting (for tool)
- agent.tool.executed
- agent.completed
- agent.failed
- agent.terminated

TaskQueue publishes:
- task.enqueued
- task.started
- task.completed  
- task.failed
- task.retrying
```

---

## 11. IMPLEMENTATION CHECKLIST

Al implementar, verificar:

- [ ] Task lifecycle states correctos
- [ ] Transitions validadas
- [ ] Owner claramente definido
- [ ] Retry con backoff exponencial
- [ ] Circuit breaker implementado
- [ ] Backpressure strategy
- [ ] Worker heartbeat
- [ ] Tool isolation
- [ ] Tool timeout
- [ ] Agent checkpointing
- [ ] Streaming funciona
- [ ] Correlation IDs propagan
- [ ] Logs estructurados
- [ ] Métricas instrumentadas
- [ ] Recovery path definido