"""
AI-OS VM/Colab API Routes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import logging

from ai_os.core.gpu.micro_vm_manager import (
from ai_os.core.security.dependencies import require_auth
from ai_os.models import TokenData

    get_micro_vm_manager,
    MicroVMManager,
    VMConfig,
    VMStatus
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vm", tags=["vm"])


class CreateVMRequest(BaseModel):
    """Request to create a VM"""
    name: Optional[str] = None
    cpu_cores: int = 2
    memory_gb: int = 12
    gpu_type: str = "T4"
    gpu_memory: int = 16
    use_proxy: bool = True
    model_name: str = "llama2"


class VMResponse(BaseModel):
    """VM information"""
    id: str
    name: str
    status: str
    ip_address: Optional[str] = None
    port: int = 8888


class ValidationResponse(BaseModel):
    """VM validation result"""
    valid: bool
    checks: dict
    details: dict


@router.post("/create", response_model=VMResponse)
async def create_vm(request: CreateVMRequest,
    user: TokenData = Depends(require_auth)
):
    """Create a new VM instance"""
    try:
        manager = get_micro_vm_manager()
        
        config = VMConfig(
            name=request.name or "",
            cpu_cores=request.cpu_cores,
            memory_gb=request.memory_gb,
            gpu_type=request.gpu_type,
            gpu_memory=request.gpu_memory,
            use_proxy=request.use_proxy,
            model_name=request.model_name
        )
        
        vm = await manager.create_vm(config)
        
        return VMResponse(
            id=vm.id,
            name=vm.name,
            status=vm.status.value,
            ip_address=vm.ip_address,
            port=vm.port
        )
        
    except Exception as e:
        logger.error(f"VM creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_vms(user: TokenData = Depends(require_auth)):
    """List all VM instances"""
    try:
        manager = get_micro_vm_manager()
        vms = await manager.list_vms()
        
        return {
            "vms": [
                {
                    "id": vm.id,
                    "name": vm.name,
                    "status": vm.status.value,
                    "ip_address": vm.ip_address,
                    "created_at": vm.created_at
                }
                for vm in vms
            ]
        }
        
    except Exception as e:
        logger.error(f"List VMs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{vm_id}", response_model=VMResponse)
async def get_vm(vm_id: str,
    user: TokenData = Depends(require_auth)
):
    """Get VM by ID"""
    try:
        manager = get_micro_vm_manager()
        vm = await manager.get_vm(vm_id)
        
        if not vm:
            raise HTTPException(status_code=404, detail="VM not found")
        
        return VMResponse(
            id=vm.id,
            name=vm.name,
            status=vm.status.value,
            ip_address=vm.ip_address,
            port=vm.port
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get VM error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{vm_id}/validate", response_model=ValidationResponse)
async def validate_vm(vm_id: str,
    user: TokenData = Depends(require_auth)
):
    """Validate a VM"""
    try:
        manager = get_micro_vm_manager()
        result = await manager.validate_vm(vm_id)
        
        return ValidationResponse(
            valid=result.valid,
            checks=result.checks,
            details=result.details
        )
        
    except Exception as e:
        logger.error(f"Validate VM error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{vm_id}")
async def delete_vm(vm_id: str,
    user: TokenData = Depends(require_auth)
):
    """Delete a VM"""
    try:
        manager = get_micro_vm_manager()
        await manager.cleanup_vm(vm_id)
        
        return {"message": f"VM {vm_id} deleted"}
        
    except Exception as e:
        logger.error(f"Delete VM error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{vm_id}/execute")
async def execute_on_vm(vm_id: str, code: str,
    user: TokenData = Depends(require_auth)
):
    """Execute code on a VM"""
    try:
        manager = get_micro_vm_manager()
        result = await manager.execute_on_vm(vm_id, code)
        
        return result
        
    except Exception as e:
        logger.error(f"Execute on VM error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup/idle")
async def cleanup_idle_vms(max_idle_minutes: int = 30,
    user: TokenData = Depends(require_auth)
):
    """Clean up idle VMs"""
    try:
        manager = get_micro_vm_manager()
        await manager.cleanup_idle(max_idle_minutes)
        
        return {"message": "Idle VMs cleaned up"}
        
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_vm_stats(user: TokenData = Depends(require_auth)):
    """Get VM manager statistics"""
    try:
        manager = get_micro_vm_manager()
        return manager.get_stats()
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def vm_health(user: TokenData = Depends(require_auth)):
    """VM service health check"""
    return {"status": "healthy"}