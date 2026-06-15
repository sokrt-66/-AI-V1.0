"""
文档管理 API
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from typing import Optional

from ..rag import doc_service
from ..schemas.schemas import ApiResponse

router = APIRouter(prefix="/api/documents", tags=["文档管理"])


@router.post("/upload", response_model=ApiResponse)
async def upload_document(file: UploadFile = File(...),
                          title: str = "",
                          category: str = "默认"):
    """上传并处理文档（解析+切片+向量化+摘要）"""
    result = doc_service.upload_and_process(file, title=title, category=category)
    return ApiResponse(message="文档处理完成", data=result)


@router.get("", response_model=ApiResponse)
async def list_documents(category: Optional[str] = None,
                         keyword: Optional[str] = None,
                         page: int = Query(1, ge=1),
                         page_size: int = Query(20, ge=1, le=200)):
    return ApiResponse(data=doc_service.list_documents(category=category, keyword=keyword,
                                                        page=page, page_size=page_size))


@router.get("/{doc_id}", response_model=ApiResponse)
async def get_document(doc_id: int):
    d = doc_service.get_document(doc_id)
    if not d:
        raise HTTPException(status_code=404, detail="文档不存在")
    return ApiResponse(data=d)


@router.delete("/{doc_id}", response_model=ApiResponse)
async def delete_document(doc_id: int):
    ok = doc_service.delete_document(doc_id)
    return ApiResponse(message="删除成功" if ok else "文档不存在", data={"success": ok})


@router.get("/categories/list", response_model=ApiResponse)
async def list_categories():
    return ApiResponse(data=doc_service.list_categories())


@router.get("/stats/summary", response_model=ApiResponse)
async def stats():
    return ApiResponse(data=doc_service.stats())
