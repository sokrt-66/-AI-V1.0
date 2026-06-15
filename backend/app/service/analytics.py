"""
运营分析、系统健康、告警服务
"""

from __future__ import annotations
import os, time, platform
try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    psutil = None
    _HAS_PSUTIL = False
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, date

from ..core.config import settings
from ..core.logger import get_logger
from ..core.database import SessionLocal
from ..models import (
    Document, ChatSession, ChatLog, Workflow, WorkflowRun,
    TokenUsage, FeatureUsage, SystemHealth, Alert, OpLog
)
from ..ai.service import get_provider

logger = get_logger("service.analytics")


# ============================================================
# 系统启动时间（全局变量）
# ============================================================
_START_TIME = time.time()


# ============================================================
# 健康检查
# ============================================================

def check_health() -> Dict[str, Any]:
    """完整系统健康状态检查"""
    try:
        if _HAS_PSUTIL:
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage(os.getcwd())
        else:
            cpu, mem, disk = 0.0, _make_mock_mem(), _make_mock_disk()
        uptime = time.time() - _START_TIME

        db_ok = _check_db()
        vector_ok = _check_vector()
        ai_ok = _check_ai()
        api_latency = _check_api_latency()

        status = "ok"
        if _HAS_PSUTIL:
            if not db_ok or cpu > 90 or mem.percent > 90:
                status = "critical"
            elif not vector_ok or cpu > 70 or mem.percent > 75 or api_latency > 5000:
                status = "warning"
        else:
            if not db_ok:
                status = "critical"
            elif not vector_ok:
                status = "warning"

        return {
            "status": status,
            "uptime_seconds": round(uptime, 1),
            "cpu_percent": round(cpu, 1),
            "memory_percent": round(mem.percent if _HAS_PSUTIL else getattr(mem, 'percent', 0), 1),
            "memory_used_gb": round(mem.used / (1024**3), 2) if _HAS_PSUTIL and hasattr(mem, 'used') else 0,
            "disk_percent": round(disk.percent, 1) if _HAS_PSUTIL and hasattr(disk, 'percent') else 0,
            "disk_free_gb": round(disk.free / (1024**3), 1) if _HAS_PSUTIL and hasattr(disk, 'free') else 0,
            "api_latency_ms": api_latency,
            "db_connected": db_ok,
            "vector_connected": vector_ok,
            "ai_available": ai_ok,
            "has_psutil": _HAS_PSUTIL,
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "status": "critical", "uptime_seconds": 0,
            "cpu_percent": 0, "memory_percent": 0, "disk_percent": 0,
            "api_latency_ms": 0, "db_connected": False,
            "vector_connected": False, "ai_available": False, "has_psutil": False,
        }


def _make_mock_mem():
    class _Mem: pass
    m = _Mem()
    m.percent = 0.0; m.used = 0
    return m


def _make_mock_disk():
    class _Disk: pass
    d = _Disk()
    d.percent = 0.0; d.free = 0
    return d


from sqlalchemy import text as _sql_text

def _check_db() -> bool:
    try:
        with SessionLocal() as db:
            db.execute(_sql_text("SELECT 1"))
        return True
    except Exception:
        return False


def _check_vector() -> bool:
    try:
        from ..rag.vector_store import get_vector_store
        vs = get_vector_store()
        vs.collection.count()
        return True
    except Exception:
        return False


def _check_ai() -> bool:
    try:
        from ..ai.service import chat
        # 3秒超时探测
        result = chat("hi", mode="cloud")
        return result and "⚠️" not in result[:5] and "错误" not in result[:5]
    except Exception:
        return False


def _check_api_latency() -> int:
    """测试 API 响应延迟（毫秒）"""
    try:
        import httpx
        from ..core.config import settings as s
        start = time.time()
        with httpx.Client(timeout=5.0) as client:
            client.post(
                f"{s.CLOUD_API_BASE}/chat/completions",
                json={
                    "model": s.CLOUD_MODEL_NAME,
                    "messages": [{"role": "user", "content": "ok"}],
                    "max_tokens": 5,
                },
                headers={"Authorization": f"Bearer {s.CLOUD_API_KEY}"},
            )
        return int((time.time() - start) * 1000)
    except Exception:
        return -1


# ============================================================
# 仪表盘统计
# ============================================================

def get_dashboard_stats() -> Dict[str, Any]:
    """仪表盘聚合统计"""
    try:
        with SessionLocal() as db:
            doc_count = db.query(Document).count()
            chunk_count = sum(d.chunk_count or 0 for d in db.query(Document).all())
            session_count = db.query(ChatSession).filter(ChatSession.is_archived == False).count()
            chat_count = db.query(ChatLog).count()
            workflow_count = db.query(Workflow).count()

            today = date.today().isoformat()
            wf_runs_today = db.query(WorkflowRun).filter(
                WorkflowRun.started_at >= datetime.combine(today, datetime.min.time())
            ).count()
            token_today = db.query(TokenUsage).filter(TokenUsage.date == today).first()
            token_today_val = token_today.total_tokens if token_today else 0

        return {
            "doc_count": doc_count,
            "chunk_count": chunk_count,
            "session_count": session_count,
            "chat_count": chat_count,
            "workflow_count": workflow_count,
            "workflow_runs_today": wf_runs_today,
            "token_today": token_today_val,
            "token_daily_limit": settings.TOKEN_DAILY_LIMIT,
            "api_latency_ms": _check_api_latency(),
            "uptime_seconds": round(time.time() - _START_TIME, 1),
        }
    except Exception as e:
        logger.error(f"仪表盘统计失败: {e}")
        return {"doc_count": 0, "chunk_count": 0, "session_count": 0,
                "chat_count": 0, "workflow_count": 0, "workflow_runs_today": 0,
                "token_today": 0, "token_daily_limit": settings.TOKEN_DAILY_LIMIT,
                "api_latency_ms": 0, "uptime_seconds": 0.0}


# ============================================================
# Token 趋势（近30天）
# ============================================================

def get_token_trend(days: int = 30) -> Dict[str, Any]:
    """近N天 Token 使用趋势（折线图数据）"""
    dates, llm_toks, emb_toks, req_counts = [], [], [], []
    with SessionLocal() as db:
        for i in range(days - 1, -1, -1):
            d = (date.today() - timedelta(days=i)).isoformat()
            dates.append(d)
            row = db.query(TokenUsage).filter(TokenUsage.date == d).first()
            llm_toks.append(row.llm_tokens if row else 0)
            emb_toks.append(row.embedding_tokens if row else 0)
            req_counts.append(row.request_count if row else 0)
    return {"dates": dates, "llm_tokens": llm_toks, "embedding_tokens": emb_toks,
            "request_counts": req_counts}


# ============================================================
# 功能使用趋势
# ============================================================

def get_feature_trend(days: int = 7) -> Dict[str, Any]:
    """近N天各功能使用量趋势"""
    dates = [(date.today() - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
    features_map = {}
    with SessionLocal() as db:
        for d in dates:
            rows = db.query(FeatureUsage).filter(FeatureUsage.date == d).all()
            for row in rows:
                if row.feature not in features_map:
                    features_map[row.feature] = [0] * days
                features_map[row.feature][dates.index(d)] = row.count
    return {"dates": dates, "features": features_map}


# ============================================================
# 告警管理
# ============================================================

def create_alert(level: str, source: str, title: str, message: str = "") -> int:
    """记录一条告警"""
    try:
        with SessionLocal() as db:
            a = Alert(level=level, source=source, title=title, message=message)
            db.add(a)
            db.commit()
            return a.id
    except Exception as e:
        logger.error(f"创建告警失败: {e}")
        return -1


def list_alerts(resolved: Optional[bool] = None, level: Optional[str] = None,
                page: int = 1, page_size: int = 20) -> Dict:
    """查询告警列表"""
    with SessionLocal() as db:
        q = db.query(Alert)
        if resolved is not None:
            q = q.filter(Alert.is_resolved == resolved)
        if level:
            q = q.filter(Alert.level == level)
        total = q.count()
        rows = q.order_by(Alert.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        items = []
        for r in rows:
            items.append({
                "id": r.id, "level": r.level, "source": r.source,
                "title": r.title, "message": r.message,
                "is_resolved": r.is_resolved,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
            })
        return {"items": items, "total": total, "page": page, "page_size": page_size}


def resolve_alert(alert_id: int) -> bool:
    """标记告警为已解决"""
    try:
        with SessionLocal() as db:
            a = db.query(Alert).filter(Alert.id == alert_id).first()
            if not a:
                return False
            a.is_resolved = True
            a.resolved_at = datetime.now()
            db.commit()
            return True
    except Exception as e:
        logger.error(f"解决告警失败: {e}")
        return False


# ============================================================
# 操作日志查询
# ============================================================

def query_oplogs(action: Optional[str] = None, status: Optional[str] = None,
                 start_date: Optional[str] = None, end_date: Optional[str] = None,
                 page: int = 1, page_size: int = 50) -> Dict:
    """分页查询操作审计日志"""
    with SessionLocal() as db:
        q = db.query(OpLog)
        if action:
            q = q.filter(OpLog.action == action)
        if status:
            q = q.filter(OpLog.status == status)
        if start_date:
            q = q.filter(OpLog.created_at >= datetime.fromisoformat(start_date))
        if end_date:
            q = q.filter(OpLog.created_at <= datetime.fromisoformat(end_date + " 23:59:59"))
        total = q.count()
        rows = q.order_by(OpLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        items = []
        for r in rows:
            items.append({
                "id": r.id, "action": r.action, "target": r.target,
                "status": r.status, "detail": r.detail,
                "ip_address": r.ip_address or "",
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
            })
        return {"items": items, "total": total, "page": page, "page_size": page_size}


# ============================================================
# 记录功能使用量
# ============================================================

def record_feature_usage(feature: str, tokens: int = 0) -> None:
    """记录功能使用量（每日汇总）"""
    try:
        today = date.today().isoformat()
        with SessionLocal() as db:
            row = db.query(FeatureUsage).filter(
                FeatureUsage.date == today,
                FeatureUsage.feature == feature
            ).first()
            if row:
                row.count += 1
                row.tokens += tokens
            else:
                db.add(FeatureUsage(date=today, feature=feature, count=1, tokens=tokens))
            db.commit()
    except Exception as e:
        logger.debug(f"记录功能使用量失败: {e}")
