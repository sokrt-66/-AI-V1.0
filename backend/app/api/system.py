"""
系统管理 API - 仪表盘、健康检查、统计分析、告警、设置
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime

from ..ai.service import set_provider_mode, get_token_stats
from ..schemas.schemas import (
    ApiResponse, SettingsUpdate, HealthResponse, DashboardStats,
    TokenTrend, FeatureTrend, TokenStatsResponse,
    AlertIn, AlertOut, OpLogFilter,
)
from ..service.analytics import (
    check_health, get_dashboard_stats, get_token_trend,
    get_feature_trend, create_alert, list_alerts, resolve_alert,
    query_oplogs, record_feature_usage,
)
from ..core.config import settings
from ..core.logger import get_logger

router = APIRouter(prefix="/api/system", tags=["系统管理"])
logger = get_logger("api.system")


# ============================================================
# 系统信息
# ============================================================

@router.get("/info", response_model=ApiResponse)
async def system_info():
    """获取系统基本信息"""
    return ApiResponse(data={
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "ai_mode": settings.AI_MODE,
        "ai_model": settings.CLOUD_MODEL_NAME,
        "ai_base": settings.CLOUD_API_BASE,
        "storage_dir": settings.STORAGE_BASE,
    })


@router.get("/health", response_model=ApiResponse)
async def health():
    """系统健康状态检查"""
    health_data = check_health()
    status_code = 200 if health_data["status"] in ("ok", "warning") else 503
    return ApiResponse(
        code=status_code if health_data["status"] == "critical" else 0,
        message=health_data["status"],
        data=health_data,
    )


# ============================================================
# 仪表盘
# ============================================================

@router.get("/dashboard/stats", response_model=ApiResponse)
async def dashboard_stats():
    """仪表盘聚合统计数据"""
    data = get_dashboard_stats()
    data["usage_percent"] = round(
        data["token_today"] / max(data["token_daily_limit"], 1) * 100, 2
    )
    return ApiResponse(data=data)


@router.get("/dashboard/token-trend", response_model=ApiResponse)
async def token_trend(days: int = Query(30, ge=7, le=90)):
    """Token 使用趋势（折线图）"""
    return ApiResponse(data=get_token_trend(days=days))


@router.get("/dashboard/feature-trend", response_model=ApiResponse)
async def feature_trend(days: int = Query(7, ge=3, le=30)):
    """功能使用趋势（柱状图）"""
    return ApiResponse(data=get_feature_trend(days=days))


# ============================================================
# Token 统计
# ============================================================

@router.get("/tokens/stats", response_model=ApiResponse)
async def token_stats():
    """今日 Token 用量"""
    stats = get_token_stats()
    if stats.get("total_tokens") and stats.get("daily_limit"):
        stats["usage_percent"] = round(
            stats["total_tokens"] / stats["daily_limit"] * 100, 2
        )
    return ApiResponse(data=stats)


# ============================================================
# 告警管理
# ============================================================

@router.get("/alerts", response_model=ApiResponse)
async def alerts(
    resolved: Optional[bool] = None,
    level: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """查询告警列表"""
    result = list_alerts(resolved=resolved, level=level, page=page, page_size=page_size)
    return ApiResponse(data=result)


@router.post("/alerts", response_model=ApiResponse)
async def create_system_alert(body: AlertIn):
    """创建告警"""
    alert_id = create_alert(level=body.level, source="manual",
                            title=body.title, message=body.message)
    return ApiResponse(message="告警已记录", data={"id": alert_id})


@router.patch("/alerts/{alert_id}/resolve", response_model=ApiResponse)
async def resolve_one_alert(alert_id: int):
    """标记告警为已解决"""
    ok = resolve_alert(alert_id)
    if not ok:
        raise HTTPException(status_code=404, detail="告警不存在")
    return ApiResponse(message="告警已标记为解决")


# ============================================================
# 操作审计日志
# ============================================================

@router.get("/logs", response_model=ApiResponse)
async def system_logs(
    action: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """分页查询操作审计日志"""
    result = query_oplogs(action=action, status=status,
                          start_date=start_date, end_date=end_date,
                          page=page, page_size=page_size)
    return ApiResponse(data=result)


# ============================================================
# 设置管理
# ============================================================

@router.get("/settings", response_model=ApiResponse)
async def get_settings():
    """获取当前系统配置"""
    return ApiResponse(data={
        "ai_mode": settings.AI_MODE,
        "ai_model": settings.CLOUD_MODEL_NAME,
        "ai_base": settings.CLOUD_API_BASE,
        "temperature": settings.TEMPERATURE,
        "top_k": settings.TOP_K,
        "chunk_size": settings.CHUNK_SIZE,
        "max_tokens": settings.MAX_TOKENS,
        "token_daily_limit": settings.TOKEN_DAILY_LIMIT,
        "enable_token_stats": settings.ENABLE_TOKEN_STATS,
    })


@router.patch("/settings", response_model=ApiResponse)
async def update_settings(body: SettingsUpdate):
    """更新系统配置（运行时生效）"""
    changes = []
    if body.ai_mode is not None:
        set_provider_mode(body.ai_mode)
        changes.append(f"ai_mode={body.ai_mode}")
    if body.temperature is not None:
        settings.TEMPERATURE = body.temperature
        changes.append(f"temperature={body.temperature}")
    if body.top_k is not None:
        settings.TOP_K = body.top_k
        changes.append(f"top_k={body.top_k}")
    if body.chunk_size is not None:
        settings.CHUNK_SIZE = body.chunk_size
        changes.append(f"chunk_size={body.chunk_size}")
    if body.max_tokens is not None:
        settings.MAX_TOKENS = body.max_tokens
        changes.append(f"max_tokens={body.max_tokens}")

    logger.info(f"[System] 配置更新: {', '.join(changes)}")
    return ApiResponse(message=f"配置已更新: {', '.join(changes)}")
