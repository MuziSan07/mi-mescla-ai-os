"""
AI-OS Process Splitter
Splits LLM, TTS, STT, Embedding, Diffusion processes across workers
"""

import asyncio
import uuid
import httpx
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
SD_BASE_URL = os.getenv("SD_BASE_URL", "http://localhost:7860")


class ProcessType(str, Enum):
    LLM = "llm"
    TTS = "tts"
    STT = "stt"
    EMBEDDING = "embedding"
    DIFFUSION = "diffusion"
    RERANK = "rerank"
    IMAGE = "image"


@dataclass
class ProcessTask:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    process_type: ProcessType = ProcessType.LLM
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    created_at: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    timeout: float = 60.0


@dataclass
class ProcessResult:
    task_id: str
    process_type: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkerInfo:
    id: str
    process_types: List[ProcessType]
    is_available: bool = True
    current_load: float = 0.0
    max_concurrent: int = 5
    last_seen: int = field(default_factory=lambda: int(datetime.now().timestamp()))


class ProcessSplitter:
    """
    Splits processes across available workers.
    Each worker handles specific process types.
    """

    def __init__(self):
        self.workers: Dict[ProcessType, List[WorkerInfo]] = {ptype: [] for ptype in ProcessType}
        self.pending_tasks: List[ProcessTask] = []
        self.processing_tasks: Dict[str, ProcessTask] = {}
        self.results: Dict[str, ProcessResult] = {}
        self.stats = {"total_processed": 0, "total_failed": 0, "avg_time": 0.0}
        self._http: Optional[httpx.AsyncClient] = None

    def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=120.0)
        return self._http

    def register_worker(self, worker: WorkerInfo):
        for ptype in worker.process_types:
            if worker not in self.workers[ptype]:
                self.workers[ptype].append(worker)
        logger.info(f"Registered worker {worker.id} for {[p.value for p in worker.process_types]}")

    def unregister_worker(self, worker_id: str):
        for workers in self.workers.values():
            for w in workers[:]:
                if w.id == worker_id:
                    workers.remove(w)

    def get_available_worker(self, process_type: ProcessType) -> Optional[WorkerInfo]:
        candidates = self.workers.get(process_type, [])
        available = [w for w in candidates if w.is_available and w.current_load < w.max_concurrent]
        if not available:
            return None
        return min(available, key=lambda w: w.current_load)

    async def route_process(self, task: ProcessTask) -> WorkerInfo:
        worker = self.get_available_worker(task.process_type)
        if not worker:
            self.pending_tasks.append(task)
            raise RuntimeError(f"No available worker for {task.process_type.value}")
        worker.current_load += 1
        return worker

    async def submit_task(self, task: ProcessTask) -> str:
        try:
            worker = await self.route_process(task)
        except RuntimeError:
            return task.id
        self.processing_tasks[task.id] = task
        asyncio.create_task(self._process_task(task, worker))
        return task.id

    async def _process_task(self, task: ProcessTask, worker: WorkerInfo):
        start = datetime.now()
        try:
            if task.process_type == ProcessType.LLM:
                result = await self._process_llm(task.payload)
            elif task.process_type == ProcessType.TTS:
                result = await self._process_tts(task.payload)
            elif task.process_type == ProcessType.STT:
                result = await self._process_stt(task.payload)
            elif task.process_type == ProcessType.EMBEDDING:
                result = await self._process_embedding(task.payload)
            elif task.process_type == ProcessType.DIFFUSION:
                result = await self._process_diffusion(task.payload)
            else:
                result = {"error": f"Unknown process type: {task.process_type}"}

            self.results[task.id] = ProcessResult(
                task_id=task.id,
                process_type=task.process_type.value,
                success=True,
                result=result
            )
            self.stats["total_processed"] += 1

        except Exception as e:
            logger.error(f"Process error: {e}")
            self.results[task.id] = ProcessResult(
                task_id=task.id,
                process_type=task.process_type.value,
                success=False,
                error=str(e)
            )
            self.stats["total_failed"] += 1

        finally:
            worker.current_load = max(0, worker.current_load - 1)
            self.processing_tasks.pop(task.id, None)
            elapsed = (datetime.now() - start).total_seconds()
            self.stats["avg_time"] = (
                self.stats["avg_time"] * (self.stats["total_processed"] - 1) + elapsed
            ) / max(1, self.stats["total_processed"])

    async def _process_llm(self, payload: Dict) -> Any:
        """Call Ollama chat API"""
        model = payload.get("model", "mistral:7b")
        messages = payload.get("messages", [])
        prompt = payload.get("prompt", "")

        if not messages and prompt:
            messages = [{"role": "user", "content": prompt}]

        response = await self._client().post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={"model": model, "messages": messages, "stream": False}
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("message", {}).get("content", "")
        return {
            "text": content,
            "tokens": len(content.split()),
            "model": model
        }

    async def _process_tts(self, payload: Dict) -> Any:
        """
        Text-to-Speech via Coqui TTS or compatible API.
        Falls back to a status response if TTS server not available.
        """
        text = payload.get("text", "")
        tts_url = payload.get("tts_url", os.getenv("TTS_BASE_URL", "http://localhost:5002"))

        try:
            response = await self._client().post(
                f"{tts_url}/api/tts",
                json={"text": text}
            )
            response.raise_for_status()
            return {
                "audio": response.content,
                "format": "wav",
                "text": text
            }
        except httpx.ConnectError:
            logger.warning("TTS server not reachable, returning status")
            return {
                "audio": None,
                "format": "wav",
                "text": text,
                "status": "tts_unavailable — start Coqui TTS or set TTS_BASE_URL"
            }

    async def _process_stt(self, payload: Dict) -> Any:
        """
        Speech-to-Text via Whisper API or compatible endpoint.
        Falls back if STT server not available.
        """
        audio_data = payload.get("audio")
        stt_url = payload.get("stt_url", os.getenv("STT_BASE_URL", "http://localhost:9000"))

        if not audio_data:
            return {"text": "", "confidence": 0.0, "error": "no audio provided"}

        try:
            files = {"audio_file": ("audio.wav", audio_data, "audio/wav")}
            response = await self._client().post(
                f"{stt_url}/asr",
                files=files,
                params={"output": "json"}
            )
            response.raise_for_status()
            data = response.json()
            return {
                "text": data.get("text", ""),
                "confidence": data.get("confidence", 0.9),
                "language": data.get("language", "en")
            }
        except httpx.ConnectError:
            logger.warning("STT server not reachable")
            return {
                "text": "",
                "confidence": 0.0,
                "status": "stt_unavailable — start Whisper API or set STT_BASE_URL"
            }

    async def _process_embedding(self, payload: Dict) -> Any:
        """Generate embeddings via Ollama embeddings endpoint"""
        model = payload.get("model", "nomic-embed-text")
        text = payload.get("text", payload.get("input", ""))

        try:
            response = await self._client().post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={"model": model, "prompt": text}
            )
            response.raise_for_status()
            data = response.json()
            embedding = data.get("embedding", [])
            return {
                "embedding": embedding,
                "dimensions": len(embedding),
                "model": model
            }
        except httpx.ConnectError:
            logger.warning("Ollama not reachable for embeddings")
            return {"embedding": [], "dimensions": 0, "error": "ollama_unavailable"}

    async def _process_diffusion(self, payload: Dict) -> Any:
        """Generate image via Stable Diffusion (Automatic1111) API"""
        prompt = payload.get("prompt", "")
        negative_prompt = payload.get("negative_prompt", "")
        steps = payload.get("steps", 20)
        width = payload.get("width", 512)
        height = payload.get("height", 512)

        if not prompt:
            return {"error": "prompt is required"}

        try:
            response = await self._client().post(
                f"{SD_BASE_URL}/sdapi/v1/txt2img",
                json={
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "steps": steps,
                    "width": width,
                    "height": height,
                }
            )
            response.raise_for_status()
            data = response.json()
            images = data.get("images", [])
            return {
                "images_base64": images,
                "image_count": len(images),
                "prompt": prompt
            }
        except httpx.ConnectError:
            return {
                "error": "Stable Diffusion not reachable. Start Automatic1111 with --api flag.",
                "sd_url": SD_BASE_URL
            }

    async def get_result(self, task_id: str) -> Optional[ProcessResult]:
        return self.results.get(task_id)

    async def distribute_batch(self, tasks: List[ProcessTask]) -> List[str]:
        task_ids = []
        for task in tasks:
            tid = await self.submit_task(task)
            task_ids.append(tid)
        return task_ids

    def get_stats(self) -> Dict:
        return {
            "stats": self.stats,
            "pending": len(self.pending_tasks),
            "processing": len(self.processing_tasks),
            "workers": {
                ptype.value: len(workers)
                for ptype, workers in self.workers.items()
            }
        }


_splitter: Optional[ProcessSplitter] = None


def get_process_splitter() -> ProcessSplitter:
    global _splitter
    if _splitter is None:
        _splitter = ProcessSplitter()
    return _splitter
