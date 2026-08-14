"""AI Operating System - Models Schema"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class ModelType(str, Enum):
    CODING = "coding"
    REASONING = "reasoning"
    VISION = "vision"
    UI_UX = "ui_ux"
    VERIFICATION = "verification"
    PLANNING = "planning"
    GPU_PLANNER = "gpu_planner"
    DIFFUSION = "diffusion"
    MONITORING = "monitoring"


class WorkerStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    DEAD = "dead"
    OFFLINE = "offline"


class WorkerType(str, Enum):
    INFERENCE = "inference"
    TRAINING = "training"
    DIFFUSION = "diffusion"
    RENDER = "render"
    MULTIMODAL = "multimodal"


class MemoryType(str, Enum):
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    SHARED = "shared"
    SEMANTIC = "semantic"


# User Models
class UserBase(BaseModel):
    username: str
    email: Optional[str] = None


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: str
    created_at: datetime
    is_active: bool = True

    class Config:
        from_attributes = True


# Token Model
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# Task Models
class TaskInput(BaseModel):
    input_data: Dict[str, Any]
    task_type: str
    priority: int = 0
    timeout: Optional[int] = None


class Task(BaseModel):
    id: str
    input_data: Dict[str, Any]
    task_type: str
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    assigned_worker: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TaskCreate(TaskInput):
    pass


class TaskUpdate(BaseModel):
    status: Optional[TaskStatus] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    assigned_worker: Optional[str] = None


# Model Configuration
class ModelConfig(BaseModel):
    name: str
    model_type: ModelType
    provider: str
    model: str
    endpoint: str
    capabilities: List[str] = []
    max_tokens: int = 4096
    temperature: float = 0.7
    enabled: bool = True


class ModelInfo(BaseModel):
    id: str
    name: str
    model_type: ModelType
    provider: str
    model: str
    endpoint: str
    capabilities: List[str] = []
    is_available: bool = True
    last_used: Optional[datetime] = None
    usage_count: int = 0


# Worker Models
class WorkerBase(BaseModel):
    name: str
    worker_type: WorkerType
    endpoint: Optional[str] = None
    capabilities: List[str] = []


class WorkerCreate(WorkerBase):
    secret_key: str


class Worker(BaseModel):
    id: str
    name: str
    worker_type: WorkerType
    status: WorkerStatus = WorkerStatus.OFFLINE
    endpoint: Optional[str] = None
    capabilities: List[str] = []
    current_task: Optional[str] = None
    last_heartbeat: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class WorkerStats(BaseModel):
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    average_duration: float = 0.0


# Memory Models
class MemoryItem(BaseModel):
    id: str
    key: str
    value: Any
    memory_type: MemoryType
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = {}
    created_at: datetime
    updated_at: Optional[datetime] = None


class MemoryStoreInput(BaseModel):
    key: str
    value: Any
    memory_type: MemoryType = MemoryType.SHORT_TERM
    metadata: Dict[str, Any] = {}


class MemoryRecallInput(BaseModel):
    query: str
    limit: int = 10
    memory_type: Optional[MemoryType] = None


# Chat Models
class ChatMessage(BaseModel):
    role: str
    content: str
    image_url: Optional[str] = None


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False


class ChatResponse(BaseModel):
    model: str
    content: str
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None


# Vision Models
class VisionRequest(BaseModel):
    image_url: str
    prompt: str
    OCR: bool = False
    object_detection: bool = False
    ui_analysis: bool = False


class BoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int
    label: str
    confidence: float


class TextRegion(BaseModel):
    text: str
    bounding_box: BoundingBox
    confidence: float


class UIComponent(BaseModel):
    component_type: str
    bounding_box: BoundingBox
    properties: Dict[str, Any] = {}


class VisionResponse(BaseModel):
    text: Optional[str] = None
    detected_objects: List[BoundingBox] = []
    text_regions: List[TextRegion] = []
    ui_components: List[UIComponent] = []


# Tool Models
class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any] = {}


class ToolExecutionInput(BaseModel):
    tool_name: str
    parameters: Dict[str, Any] = {}


class ToolResult(BaseModel):
    tool_name: str
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time: float


# Event Models
class Event(BaseModel):
    id: str
    event_type: str
    data: Dict[str, Any] = {}
    timestamp: datetime


# Health Models
class HealthStatus(BaseModel):
    status: str
    timestamp: datetime
    components: Dict[str, str] = {}


# Audit Models
class AuditResult(BaseModel):
    id: str
    timestamp: datetime
    passed: bool
    issues: List[Dict[str, Any]] = []
    corrections_applied: List[str] = []


class CorrectionInput(BaseModel):
    issue_id: str
    action: str
    parameters: Dict[str, Any] = {}