"""
会话管理服务 - 会话 CRUD、导出、多会话管理
"""

from __future__ import annotations
import os, json, uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from ..core.config import settings
from ..core.logger import get_logger
from ..core.database import SessionLocal
from ..models import ChatSession, ChatLog

logger = get_logger("rag.session")


def get_or_create_session(session_id: str) -> Dict[str, Any]:
    """获取或创建会话"""
    with SessionLocal() as db:
        s = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if not s:
            s = ChatSession(session_id=session_id, title="新对话")
            db.add(s)
            db.commit()
            db.refresh(s)
        return _session_to_dict(s)


def _session_to_dict(s: ChatSession) -> Dict[str, Any]:
    return {
        "session_id": s.session_id,
        "title": s.title,
        "model": s.model or "",
        "message_count": s.message_count or 0,
        "token_usage": s.token_usage or 0,
        "is_favorite": s.is_favorite,
        "is_archived": s.is_archived,
        "tags": s.tags or "",
        "created_at": s.created_at.strftime("%Y-%m-%d %H:%M:%S") if s.created_at else "",
        "updated_at": s.updated_at.strftime("%Y-%m-%d %H:%M:%S") if s.updated_at else "",
    }


def list_sessions(favorite: bool = False, archived: bool = False,
                  keyword: str = "", page: int = 1, page_size: int = 20) -> Dict:
    """分页查询会话列表"""
    with SessionLocal() as db:
        q = db.query(ChatSession)
        if favorite:
            q = q.filter(ChatSession.is_favorite == True)
        if archived:
            q = q.filter(ChatSession.is_archived == True)
        else:
            q = q.filter(ChatSession.is_archived == False)
        if keyword:
            q = q.filter(ChatSession.title.like(f"%{keyword}%"))
        total = q.count()
        rows = q.order_by(ChatSession.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return {"items": [_session_to_dict(r) for r in rows], "total": total, "page": page, "page_size": page_size}


def update_session(session_id: str, title: Optional[str] = None,
                    is_favorite: Optional[bool] = None,
                    is_archived: Optional[bool] = None,
                    tags: Optional[str] = None) -> Optional[Dict]:
    """更新会话元信息"""
    with SessionLocal() as db:
        s = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if not s:
            return None
        if title is not None:
            s.title = title
        if is_favorite is not None:
            s.is_favorite = is_favorite
        if is_archived is not None:
            s.is_archived = is_archived
        if tags is not None:
            s.tags = tags
        s.updated_at = datetime.now()
        db.commit()
        db.refresh(s)
        return _session_to_dict(s)


def delete_session(session_id: str) -> bool:
    """删除会话及所有聊天记录"""
    with SessionLocal() as db:
        s = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if not s:
            return False
        db.query(ChatLog).filter(ChatLog.session_id == session_id).delete()
        db.delete(s)
        db.commit()
        return True


def increment_session_stats(session_id: str, tokens: int) -> None:
    """问答后更新会话统计"""
    try:
        with SessionLocal() as db:
            s = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
            if s:
                s.message_count = (s.message_count or 0) + 1
                s.token_usage = (s.token_usage or 0) + tokens
                s.updated_at = datetime.now()
                db.commit()
    except Exception as e:
        logger.debug(f"更新会话统计失败: {e}")


def export_session(session_id: str, format: str = "markdown",
                   include_sources: bool = True,
                   include_metadata: bool = True) -> Dict[str, Any]:
    """导出会话为 Markdown / JSON / HTML"""
    with SessionLocal() as db:
        s = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if not s:
            raise ValueError(f"会话 {session_id} 不存在")

        logs = db.query(ChatLog).filter(
            ChatLog.session_id == session_id
        ).order_by(ChatLog.created_at.asc()).all()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c if c.isalnum() else "_" for c in s.title)[:30]
        file_name = f"chat_export_{safe_title}_{timestamp}"
        export_dir = os.path.join(settings.EXPORT_DIR)
        os.makedirs(export_dir, exist_ok=True)

        if format == "json":
            content = _build_json_export(s, logs, include_metadata)
            file_name += ".json"
            path = os.path.join(export_dir, file_name)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(json.loads(content), f, ensure_ascii=False, indent=2)
        elif format == "html":
            content = _build_html_export(s, logs, include_sources, include_metadata)
            file_name += ".html"
            path = os.path.join(export_dir, file_name)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        else:  # markdown
            content = _build_markdown_export(s, logs, include_sources, include_metadata)
            file_name += ".md"
            path = os.path.join(export_dir, file_name)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

        size = os.path.getsize(path)
        return {"file_path": path, "file_name": file_name, "size": size, "format": format}


def _build_markdown_export(s: ChatSession, logs: List[ChatLog],
                           include_sources: bool, include_metadata: bool) -> str:
    lines = [
        f"# {s.title}",
        "",
        f"> **导出会话** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    if include_metadata:
        lines += [
            f"- 模型: {s.model or 'N/A'}",
            f"- 消息轮次: {len(logs)}",
            f"- Token消耗: {s.token_usage or 0:,}",
            f"- 创建时间: {s.created_at.strftime('%Y-%m-%d %H:%M:%S') if s.created_at else 'N/A'}",
        ]
    lines.append("")
    for log in logs:
        lines.append(f"## 用户")
        lines.append(log.question or "")
        lines.append("")
        lines.append(f"## AI 助手")
        lines.append(log.answer or "")
        if include_sources and log.sources:
            srcs = log.sources if isinstance(log.sources, list) else []
            for i, src in enumerate(srcs, 1):
                lines.append(f"  > 来源{i}: **{src.get('title', '')}** ({src.get('score', 0):.2%})")
        lines.append("")
        lines.append(f"*{log.created_at.strftime('%Y-%m-%d %H:%M:%S') if log.created_at else ''}*")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def _build_json_export(s: ChatSession, logs: List[ChatLog], include_metadata: bool) -> str:
    data = {"session": _session_to_dict(s), "messages": []}
    for log in logs:
        msg = {
            "role": "user",
            "content": log.question,
            "timestamp": log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else "",
        }
        data["messages"].append(msg)
        msg2 = {
            "role": "assistant",
            "content": log.answer,
            "sources": log.sources if include_metadata else [],
            "tokens_used": log.tokens_used,
            "latency_ms": log.latency_ms,
            "model": log.model,
        }
        data["messages"].append(msg2)
    return json.dumps(data, ensure_ascii=False, indent=2)


def _build_html_export(s: ChatSession, logs: List[ChatLog],
                       include_sources: bool, include_metadata: bool) -> str:
    md = _build_markdown_export(s, logs, include_sources, include_metadata)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{s.title} - 导出会话</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:800px;margin:40px auto;padding:0 20px;background:#fafafa;color:#333}}
  h1{{color:#1a1a2e;border-bottom:2px solid #1890ff;padding-bottom:8px}}
  h2{{color:#16213e;margin-top:28px;font-size:1.1em}}
  blockquote{{background:#e8f4fd;border-left:4px solid #1890ff;padding:12px 16px;margin:8px 0;border-radius:4px}}
  .meta{{color:#666;font-size:.9em;background:#f5f5f5;padding:10px;border-radius:6px}}
  .source{{color:#555;font-size:.88em;background:#fffbe6;padding:6px 12px;border-radius:4px}}
  .divider{{border:none;border-top:1px dashed #ccc;margin:20px 0}}
  hr{{border:none;border-top:1px dashed #ccc;margin:20px 0}}
  .footer{{text-align:center;color:#999;font-size:.85em;margin-top:40px}}
</style>
</head>
<body>
<div id="content"></div>
<div class="footer">由 轻企AI智能办公系统 生成 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script>document.getElementById('content').innerHTML=marked.parse({json.dumps(md)});</script>
</body>
</html>"""
