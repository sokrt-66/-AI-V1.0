"""
文档服务：上传、解析、入库、查询、删除、总结
"""

import os
import shutil
from typing import List, Dict, Optional, Any
from datetime import datetime

from .parser import parse_document
from .chunker import chunk_document
from .vector_store import get_vector_store
from .engine import summarize, extract_key_points
from ..core.config import settings
from ..core.logger import get_logger
from ..core.database import SessionLocal
from ..core.utils import safe_filename, gen_id, human_size
from ..models import Document, OpLog

logger = get_logger("rag.doc_service")


def _op_log(action: str, target: str, status: str = "ok", detail: str = "") -> None:
    try:
        with SessionLocal() as db:
            db.add(OpLog(action=action, target=target, status=status, detail=detail))
            db.commit()
    except Exception:
        pass


def upload_and_process(file_storage, title: str = "", category: str = "默认") -> Dict[str, Any]:
    """上传文件并处理入库"""
    fn = safe_filename(file_storage.filename or gen_id("file"))
    ext = os.path.splitext(fn)[1].lower()
    if not ext:
        ext = ".txt"
        fn += ext

    dst_dir = settings.UPLOAD_DIR
    os.makedirs(dst_dir, exist_ok=True)
    dst_path = os.path.join(dst_dir, f"{gen_id('doc')}_{fn}")

    with open(dst_path, "wb") as out:
        shutil.copyfileobj(file_storage.file, out)
    logger.info(f"[Doc] 已保存文件: {dst_path}")

    # 解析
    parsed = parse_document(dst_path)
    # 切片
    chunks = chunk_document(parsed["content"])

    # 入库到 SQL
    doc = Document(
        title=title or parsed["file_name"],
        file_name=parsed["file_name"],
        file_size=parsed["file_size"],
        file_type=parsed["file_type"],
        content_length=parsed["content_length"],
        chunk_count=len(chunks),
        category=category,
        status="parsing",
        storage_path=dst_path,
    )
    with SessionLocal() as db:
        db.add(doc)
        db.commit()
        db.refresh(doc)
        doc_id = doc.id

    # 向量化
    vs = get_vector_store()
    try:
        added = vs.add_chunks(doc_id, doc.title, chunks)
    except Exception as e:
        logger.error(f"向量化失败: {e}")
        added = 0

    # 生成摘要
    summary_text = summarize(parsed["content"]) if parsed["content"] else ""

    with SessionLocal() as db:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.status = "done"
            doc.chunk_count = added
            doc.summary = summary_text
            db.commit()

    _op_log("upload_document", f"doc={doc_id} {fn}", "ok",
            f"chunks={added}, size={human_size(parsed['file_size'])}")

    return {
        "id": doc_id,
        "title": title or parsed["file_name"],
        "file_name": fn,
        "file_size": parsed["file_size"],
        "content_length": parsed["content_length"],
        "chunk_count": added,
        "file_type": parsed["file_type"],
        "status": "done",
        "summary": summary_text,
        "key_points": extract_key_points(parsed["content"])[:5] if parsed["content"] else [],
    }


def list_documents(category: Optional[str] = None, keyword: Optional[str] = None,
                   page: int = 1, page_size: int = 20) -> Dict:
    """分页查询文档"""
    with SessionLocal() as db:
        q = db.query(Document)
        if category:
            q = q.filter(Document.category == category)
        if keyword:
            q = q.filter(Document.title.like(f"%{keyword}%"))
        total = q.count()
        rows = q.order_by(Document.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        items = []
        for r in rows:
            items.append({
                "id": r.id,
                "title": r.title,
                "file_name": r.file_name,
                "file_size": r.file_size,
                "file_type": r.file_type,
                "content_length": r.content_length,
                "chunk_count": r.chunk_count,
                "category": r.category,
                "status": r.status,
                "summary": (r.summary or "")[:120],
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
            })
        return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_document(doc_id: int) -> Optional[Dict]:
    with SessionLocal() as db:
        r = db.query(Document).filter(Document.id == doc_id).first()
        if not r:
            return None
        with open(r.storage_path, "r", encoding="utf-8", errors="ignore") if r.file_type in ("txt", "md", "csv") else _dummy_ctx():
            content_preview = ""
        try:
            if r.file_type in ("txt", "md", "csv"):
                with open(r.storage_path, "r", encoding="utf-8", errors="ignore") as f:
                    content_preview = f.read(1000)
        except Exception:
            content_preview = ""
        return {
            "id": r.id,
            "title": r.title,
            "file_name": r.file_name,
            "file_size": r.file_size,
            "file_type": r.file_type,
            "content_length": r.content_length,
            "chunk_count": r.chunk_count,
            "category": r.category,
            "status": r.status,
            "summary": r.summary,
            "content_preview": content_preview,
            "key_points": extract_key_points(content_preview or (r.summary or ""))[:5],
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
        }


class _dummy_ctx:
    def __enter__(self):
        return self
    def __exit__(self, *a):
        pass


def delete_document(doc_id: int) -> bool:
    with SessionLocal() as db:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return False
        # 删除向量
        try:
            vs = get_vector_store()
            vs.delete_by_document(doc_id)
        except Exception as e:
            logger.warning(f"删除向量失败: {e}")
        # 删除文件
        try:
            if doc.storage_path and os.path.exists(doc.storage_path):
                os.remove(doc.storage_path)
        except Exception:
            pass
        db.delete(doc)
        db.commit()
    _op_log("delete_document", f"doc={doc_id}")
    return True


def list_categories() -> List[str]:
    with SessionLocal() as db:
        rows = db.query(Document.category).distinct().all()
        return [r[0] for r in rows if r[0]]


def stats() -> Dict:
    with SessionLocal() as db:
        total = db.query(Document).count()
        total_size = db.query(Document).all()
        size = sum((r.file_size or 0) for r in total_size)
        chunks = sum((r.chunk_count or 0) for r in total_size)
    vs = get_vector_store()
    return {
        "doc_count": total,
        "total_size": size,
        "chunk_count": chunks,
        "vector_count": vs.get_stats().get("total_chunks", 0),
    }
