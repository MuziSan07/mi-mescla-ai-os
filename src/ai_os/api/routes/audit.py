"""
AI-OS Audit API Routes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["audit"])  # prefix supplied by main.py (/api/v1/audit)


@router.get("/run")
async def run_audit():
    """Run full project audit"""
    from ai_os.utils.project_auditor import get_project_auditor
    
    try:
        auditor = get_project_auditor()
        report = await auditor.run_full_audit()
        
        return {
            "status": "complete",
            "files": report.total_files,
            "folders": report.total_folders,
            "functions": report.total_functions,
            "classes": report.total_classes,
            "apis": report.total_apis,
            "lines": report.total_lines,
            "integration_score": report.integration_score,
            "health_score": report.health_score,
        }
        
    except Exception as e:
        logger.error(f"Audit error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report")
async def get_audit_report():
    """Get audit report"""
    from ai_os.utils.project_auditor import get_project_auditor
    
    try:
        auditor = get_project_auditor()
        return auditor.generate_report()
        
    except Exception as e:
        logger.error(f"Report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/autocorrect")
async def run_autocorrect():
    """Run auto-correction"""
    from ai_os.utils.project_auditor import get_project_auditor
    
    try:
        auditor = get_project_auditor()
        
        # First run audit if not done
        await auditor.run_full_audit()
        
        # Then autocorrect
        results = await auditor.run_autocorrect()
        
        return {
            "status": "complete",
            "fixed": results.get("fixed", []),
            "created": results.get("created", []),
            "warnings": results.get("warnings", []),
        }
        
    except Exception as e:
        logger.error(f"Autocorrect error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/structure")
async def get_structure():
    """Get project structure map"""
    from ai_os.utils.project_auditor import get_project_auditor
    
    try:
        auditor = get_project_auditor()
        report = await auditor.run_full_audit()
        
        # Build tree structure
        def build_tree(path: str, depth: int = 0) -> list:
            if depth > 3:
                return []
            
            children = []
            for folder in report.folders.values():
                if folder.path.count('/') == path.count('/') + 1 and folder.path.startswith(path + '/'):
                    children.append({
                        "name": folder.path.split('/')[-1],
                        "type": "folder",
                        "files": folder.file_count,
                        "children": []
                    })
            
            return children
        
        tree = build_tree("/", 0)
        
        return {
            "tree": tree,
            "stats": {
                "files": report.total_files,
                "folders": report.total_folders,
                "functions": report.total_functions,
                "apis": report.total_apis,
            }
        }
        
    except Exception as e:
        logger.error(f"Structure error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dependencies")
async def get_dependencies():
    """Get dependency map"""
    from ai_os.utils.project_auditor import get_project_auditor
    
    try:
        auditor = get_project_auditor()
        report = auditor.report
        
        return {
            "dependencies": [
                {"name": d.name, "version": d.version}
                for d in report.dependencies.values()
            ]
        }
        
    except Exception as e:
        logger.error(f"Dependencies error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/apis")
async def get_api_map():
    """Get API map"""
    from ai_os.utils.project_auditor import get_project_auditor
    
    try:
        auditor = get_project_auditor()
        report = auditor.report
        
        return {
            "apis": [
                {
                    "path": api.path,
                    "method": api.method,
                    "file": api.file_path,
                    "line": api.line_number
                }
                for api in report.apis
            ]
        }
        
    except Exception as e:
        logger.error(f"API map error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def audit_health():
    """Audit system health check"""
    return {"status": "healthy", "auditor": "active"}