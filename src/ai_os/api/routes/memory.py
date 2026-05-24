"""AI Operating System - Memory API Route"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from datetime import datetime

from ai_os.models.schemas import (
    MemoryItem, MemoryStoreInput, MemoryRecallInput, MemoryType
)
from ai_os.core.memory.short_term import get_memory_store

router = APIRouter()


@router.get("/", response_model=list[MemoryItem])
async def list_memories(
    memory_type: Optional[str] = None,
    limit: int = 100
):
    """List all memories"""
    memory_store = get_memory_store()
    
    mt = None
    if memory_type:
        try:
            mt = MemoryType(memory_type)
        except ValueError:
            pass
    
    return await memory_store.list_memories(memory_type=mt, limit=limit)


@router.post("/store")
async def store_memory(input_data: MemoryStoreInput):
    """Store a memory"""
    memory_store = get_memory_store()
    memory = await memory_store.store(input_data)
    return memory


@router.post("/recall", response_model=list[MemoryItem])
async def recall_memory(input_data: MemoryRecallInput):
    """Recall memories"""
    memory_store = get_memory_store()
    memories = await memory_store.recall(input_data)
    return memories


@router.get("/{memory_id}", response_model=MemoryItem)
async def get_memory(memory_id: str):
    """Get a specific memory"""
    memory_store = get_memory_store()
    
    # This is a simplified look-up
    memories = await memory_store.list_memories(limit=1000)
    for memory in memories:
        if memory.id == memory_id:
            return memory
    
    raise HTTPException(status_code=404, detail="Memory not found")


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a memory"""
    memory_store = get_memory_store()
    result = await memory_store.delete(memory_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Memory not found")
    
    return {"status": "deleted"}