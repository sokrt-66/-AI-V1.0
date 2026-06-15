"""
工作流 API
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Optional, Dict, Any

from ..workflow import service as wf_service
from ..schemas.schemas import ApiResponse, WorkflowIn, WorkflowRunRequest

router = APIRouter(prefix="/api/workflows", tags=["自动化工作流"])


@router.post("", response_model=ApiResponse)
async def create_workflow(req: WorkflowIn):
    result = wf_service.create_workflow(
        name=req.name, type=req.type, cron=req.cron,
        params=req.params, enabled=req.enabled
    )
    return ApiResponse(message="创建成功", data=result)


@router.get("", response_model=ApiResponse)
async def list_workflows(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200)):
    return ApiResponse(data=wf_service.list_workflows(page=page, page_size=page_size))


@router.get("/{wf_id}", response_model=ApiResponse)
async def get_workflow(wf_id: int):
    r = wf_service.get_workflow(wf_id)
    if not r:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return ApiResponse(data=r)


@router.put("/{wf_id}", response_model=ApiResponse)
async def update_workflow(wf_id: int, req: WorkflowIn):
    r = wf_service.update_workflow(
        wf_id=wf_id, name=req.name, type=req.type, cron=req.cron,
        params=req.params, enabled=req.enabled
    )
    return ApiResponse(message="更新成功", data=r)


@router.delete("/{wf_id}", response_model=ApiResponse)
async def delete_workflow(wf_id: int):
    ok = wf_service.delete_workflow(wf_id)
    return ApiResponse(message="删除成功" if ok else "工作流不存在", data={"success": ok})


@router.post("/{wf_id}/run", response_model=ApiResponse)
async def run_workflow(wf_id: int, body: Dict[str, Any] = Body(default_factory=dict)):
    result = wf_service.run_workflow(wf_id, run_params=body or {})
    return ApiResponse(message="执行完成", data=result)


@router.get("/{wf_id}/runs", response_model=ApiResponse)
async def list_runs(wf_id: int, limit: int = Query(20, ge=1, le=500)):
    return ApiResponse(data=wf_service.workflow_runs(wf_id, limit=limit))


@router.get("/jobs/scheduled", response_model=ApiResponse)
async def list_scheduled_jobs():
    from ..workflow.scheduler import list_jobs
    return ApiResponse(data=list_jobs())
