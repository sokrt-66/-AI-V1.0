"""
工作流 CRUD 服务
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy import desc

from .workflows import run_workflow_by_type, WORKFLOW_REGISTRY
from .scheduler import schedule_workflow, unschedule_workflow, execute_now, list_jobs
from ..core.database import SessionLocal
from ..core.logger import get_logger
from ..models import Workflow, WorkflowRun

logger = get_logger("wf.service")


def create_workflow(name: str, type: str, cron: str = "", params: Optional[Dict] = None,
                    enabled: bool = True) -> Dict:
    if type not in WORKFLOW_REGISTRY:
        return {"success": False, "error": f"暂不支持的工作流类型: {type}"}
    with SessionLocal() as db:
        wf = Workflow(name=name, type=type, cron=cron, params=params or {}, enabled=enabled)
        db.add(wf)
        db.commit()
        db.refresh(wf)
        if cron:
            schedule_workflow(wf.id, cron)
        return {"success": True, "id": wf.id, "name": name, "type": type}


def list_workflows(page: int = 1, page_size: int = 20) -> Dict:
    with SessionLocal() as db:
        q = db.query(Workflow)
        total = q.count()
        rows = q.order_by(desc(Workflow.id)).offset((page - 1) * page_size).limit(page_size).all()
        jobs = {j["id"]: j["next_run_at"] for j in list_jobs()}
        items = []
        for r in rows:
            items.append({
                "id": r.id,
                "name": r.name,
                "type": r.type,
                "cron": r.cron,
                "params": r.params or {},
                "enabled": r.enabled,
                "last_run_at": r.last_run_at.strftime("%Y-%m-%d %H:%M:%S") if r.last_run_at else "",
                "last_status": r.last_status,
                "next_run_at": jobs.get(f"wf_{r.id}", ""),
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
            })
        return {"items": items, "total": total, "types": list(WORKFLOW_REGISTRY.keys())}


def get_workflow(wf_id: int) -> Optional[Dict]:
    with SessionLocal() as db:
        r = db.query(Workflow).filter(Workflow.id == wf_id).first()
        if not r:
            return None
        return {
            "id": r.id,
            "name": r.name,
            "type": r.type,
            "cron": r.cron,
            "params": r.params or {},
            "enabled": r.enabled,
        }


def update_workflow(wf_id: int, name: Optional[str] = None, type: Optional[str] = None,
                    cron: Optional[str] = None, params: Optional[Dict] = None,
                    enabled: Optional[bool] = None) -> Dict:
    with SessionLocal() as db:
        wf = db.query(Workflow).filter(Workflow.id == wf_id).first()
        if not wf:
            return {"success": False, "error": "工作流不存在"}
        if name is not None:
            wf.name = name
        if type is not None:
            if type not in WORKFLOW_REGISTRY:
                return {"success": False, "error": f"不支持的工作流类型: {type}"}
            wf.type = type
        if cron is not None:
            wf.cron = cron
            if cron:
                schedule_workflow(wf.id, cron)
            else:
                unschedule_workflow(wf.id)
        if params is not None:
            wf.params = params
        if enabled is not None:
            wf.enabled = enabled
            if not enabled:
                unschedule_workflow(wf.id)
            elif wf.cron:
                schedule_workflow(wf.id, wf.cron)
        db.commit()
        return {"success": True, "id": wf.id}


def delete_workflow(wf_id: int) -> bool:
    with SessionLocal() as db:
        wf = db.query(Workflow).filter(Workflow.id == wf_id).first()
        if not wf:
            return False
        unschedule_workflow(wf_id)
        db.query(WorkflowRun).filter(WorkflowRun.workflow_id == wf_id).delete()
        db.delete(wf)
        db.commit()
    return True


def run_workflow(wf_id: int, run_params: Optional[Dict] = None) -> Dict:
    with SessionLocal() as db:
        wf = db.query(Workflow).filter(Workflow.id == wf_id).first()
        if not wf:
            return {"success": False, "error": "工作流不存在"}
        params = {**(wf.params or {}), **(run_params or {})}
        result = run_workflow_by_type(wf.type, params)
        run = WorkflowRun(
            workflow_id=wf.id,
            status=result.get("status", "success"),
            output=str(result.get("output", "")),
            detail=result,
        )
        db.add(run)
        wf.last_run_at = run.created_at
        wf.last_status = run.status
        db.commit()
    return {"success": True, "result": result}


def workflow_runs(wf_id: int, limit: int = 20) -> List[Dict]:
    with SessionLocal() as db:
        rows = db.query(WorkflowRun).filter(WorkflowRun.workflow_id == wf_id).order_by(
            desc(WorkflowRun.id)).limit(limit).all()
        return [
            {
                "id": r.id,
                "workflow_id": r.workflow_id,
                "status": r.status,
                "output": r.output,
                "detail": r.detail or {},
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
            }
            for r in rows
        ]
