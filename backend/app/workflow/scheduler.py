"""
APScheduler 调度器 - 负责工作流定时触发
"""

from __future__ import annotations
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .workflows import run_workflow_by_type
from ..core.logger import get_logger
from ..core.database import SessionLocal
from ..models import Workflow, WorkflowRun

logger = get_logger("wf.scheduler")

_scheduler: Optional[BackgroundScheduler] = None


def _execute_workflow(workflow_id: int) -> None:
    """调度执行器"""
    with SessionLocal() as db:
        wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
        if not wf or not wf.enabled:
            return
        logger.info(f"[Scheduler] 触发工作流: id={wf.id} name={wf.name} type={wf.type}")
        result = run_workflow_by_type(wf.type, wf.params or {})
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


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        _scheduler.start()
        logger.info("[Scheduler] 调度器已启动")
        _reload_from_db()
    return _scheduler


def _reload_from_db() -> None:
    """应用启动时把数据库中已配置 cron 的工作流加入调度"""
    if not _scheduler:
        return
    with SessionLocal() as db:
        rows = db.query(Workflow).filter(Workflow.cron != "").all()
        for wf in rows:
            try:
                job_id = f"wf_{wf.id}"
                trigger = CronTrigger.from_crontab(wf.cron)
                if _scheduler.get_job(job_id):
                    _scheduler.reschedule_job(job_id, trigger=trigger)
                else:
                    _scheduler.add_job(
                        _execute_workflow,
                        trigger=trigger,
                        id=job_id,
                        args=[wf.id],
                        misfire_grace_time=3600,
                        coalesce=True,
                    )
                logger.info(f"[Scheduler] 已注册工作流 {wf.name} cron={wf.cron}")
            except Exception as e:
                logger.warning(f"[Scheduler] 注册工作流 {wf.name} 失败: {e}")


def schedule_workflow(workflow_id: int, cron: str) -> bool:
    """新增/更新工作流的定时调度"""
    s = get_scheduler()
    job_id = f"wf_{workflow_id}"
    try:
        trigger = CronTrigger.from_crontab(cron)
        if s.get_job(job_id):
            s.reschedule_job(job_id, trigger=trigger)
        else:
            s.add_job(_execute_workflow, trigger=trigger, id=job_id, args=[workflow_id],
                      misfire_grace_time=3600, coalesce=True)
        return True
    except Exception as e:
        logger.error(f"[Scheduler] 配置失败: {e}")
        return False


def unschedule_workflow(workflow_id: int) -> None:
    s = get_scheduler()
    job_id = f"wf_{workflow_id}"
    if s.get_job(job_id):
        s.remove_job(job_id)


def execute_now(workflow_id: int) -> dict:
    """立即执行一次"""
    _execute_workflow(workflow_id)
    with SessionLocal() as db:
        run = db.query(WorkflowRun).filter(WorkflowRun.workflow_id == workflow_id).order_by(
            WorkflowRun.id.desc()).first()
        if run:
            return {
                "workflow_id": run.workflow_id,
                "status": run.status,
                "output": run.output,
                "created_at": run.created_at.strftime("%Y-%m-%d %H:%M:%S") if run.created_at else "",
            }
    return {"status": "executed"}


def list_jobs() -> list:
    s = get_scheduler()
    return [
        {"id": j.id, "next_run_at": j.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if j.next_run_time else ""}
        for j in s.get_jobs()
    ]


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("[Scheduler] 调度器已关闭")
