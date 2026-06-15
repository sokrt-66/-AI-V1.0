"""
RAG 问答 API - 完整商业版
包含：普通问答、流式问答、会话管理、历史记录、导出
"""

import time
from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional

from ..rag.engine import answer
from ..rag.session_service import (
    list_sessions, update_session, delete_session, export_session,
    get_or_create_session, increment_session_stats,
)
from ..service.analytics import record_feature_usage
from ..core.database import SessionLocal
from ..core.logger import get_logger
from ..models import ChatLog, ChatSession
from ..schemas.schemas import (
    ApiResponse, ChatRequest, SessionUpdate,
    ChatExportRequest, ChatExportResponse,
)

router = APIRouter(prefix="/api/chat", tags=["智能问答"])
logger = get_logger("api.chat")


@router.post("", response_model=ApiResponse)
async def chat(req: ChatRequest, request: Request):
    """智能问答主接口"""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="请输入问题")

    start_ms = int(time.time() * 1000)
    session_id = req.session_id or "default"

    # 确保会话存在
    get_or_create_session(session_id)

    # 执行问答（engine 内部已做容错）
    result = answer(
        question=req.question,
        session_id=session_id,
        top_k=req.top_k,
        temperature=req.temperature,
        use_rag=req.use_rag,
        document_ids=req.document_ids,
    )

    latency_ms = int(time.time() * 1000) - start_ms

    # 更新会话统计
    increment_session_stats(session_id, result.get("tokens_used", 0))

    # 记录功能使用
    record_feature_usage("rag_chat", result.get("tokens_used", 0))

    # 兼容：同步 latency_ms 到响应
    result["latency_ms"] = latency_ms
    result["session_id"] = session_id
    result["model"] = result.get("mode", "")

    return ApiResponse(message="问答完成", data=result)


@router.get("/history", response_model=ApiResponse)
async def chat_history(session_id: str = "default", limit: int = Query(50, ge=1, le=500)):
    """获取会话历史（倒序）"""
    with SessionLocal() as db:
        rows = (
            db.query(ChatLog)
            .filter(ChatLog.session_id == session_id)
            .order_by(ChatLog.id.desc())
            .limit(limit)
            .all()
        )
        items = [
            {
                "id": r.id,
                "question": r.question,
                "answer": r.answer,
                "sources": r.sources if r.sources else [],
                "source_count": r.source_count or 0,
                "tokens_used": r.tokens_used or 0,
                "latency_ms": r.latency_ms or 0,
                "model": r.model or "",
                "search_mode": r.search_mode or "vector",
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
            }
            for r in reversed(rows)
        ]
    return ApiResponse(data={"items": items, "total": len(items), "session_id": session_id})


# ============================================================
# 会话管理
# ============================================================

@router.get("/sessions", response_model=ApiResponse)
async def get_sessions(
    favorite: bool = False,
    archived: bool = False,
    keyword: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """会话列表（支持收藏、归档、关键词搜索）"""
    result = list_sessions(favorite=favorite, archived=archived,
                           keyword=keyword, page=page, page_size=page_size)
    return ApiResponse(data=result)


@router.patch("/sessions/{session_id}", response_model=ApiResponse)
async def patch_session(session_id: str, body: SessionUpdate):
    """更新会话（重命名、收藏、归档、标签）"""
    result = update_session(
        session_id,
        title=body.title,
        is_favorite=body.is_favorite,
        is_archived=body.is_archived,
        tags=body.tags,
    )
    if not result:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ApiResponse(message="更新成功", data=result)


@router.delete("/sessions/{session_id}", response_model=ApiResponse)
async def remove_session(session_id: str):
    """删除会话及所有聊天记录"""
    ok = delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ApiResponse(message="会话已删除")


@router.post("/sessions", response_model=ApiResponse)
async def create_new_session():
    """创建新会话"""
    import uuid
    session_id = uuid.uuid4().hex[:12]
    result = get_or_create_session(session_id)
    return ApiResponse(message="新会话已创建", data=result)


# ============================================================
# 对话导出
# ============================================================

@router.post("/export", response_model=ApiResponse)
async def export_chat(body: ChatExportRequest):
    """导出会话为 Markdown / JSON / HTML"""
    try:
        result = export_session(
            session_id=body.session_id,
            format=body.format,
            include_sources=body.include_sources,
            include_metadata=body.include_metadata,
        )
        return ApiResponse(message="导出成功", data=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"导出失败: {e}")
        raise HTTPException(status_code=500, detail=f"导出失败: {e}")
