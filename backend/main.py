"""
FastAPI 主入口 - 轻企AI智能办公系统 V1.0
"""

import os
import sys
import json
import atexit
import signal
import traceback
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# 把项目根目录加到 Python 路径，确保 import 能在各种启动方式下工作
BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(ROOT_DIR))

from app.core.config import settings, ensure_dirs, get_settings  # noqa: E402
from app.core.logger import get_logger  # noqa: E402
from app.core.database import init_db  # noqa: E402
from app.api.documents import router as documents_router  # noqa: E402
from app.api.chat import router as chat_router  # noqa: E402
from app.api.workflows import router as workflows_router  # noqa: E402
from app.api.system import router as system_router  # noqa: E402

logger = get_logger("main")

app = FastAPI(
    title="轻企AI智能办公系统",
    description="企业轻量化AI RAG知识库 + 自动化工作流",
    version=settings.APP_VERSION,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    ensure_dirs()
    init_db()
    logger.info(f"[{settings.APP_NAME} V{settings.APP_VERSION}] 启动完成，AI 模式: {settings.AI_MODE}")


@app.on_event("shutdown")
def on_shutdown():
    try:
        from app.workflow.scheduler import shutdown_scheduler
        shutdown_scheduler()
    except Exception:
        pass
    logger.info("系统正常关闭")


# 统一异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    logger.error(f"未捕获异常: {request.method} {request.url} -> {exc}\n{tb}")
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": f"系统异常: {exc}", "data": None},
    )


# =============== 前端静态页面 ===============
FRONTEND_DIR = ROOT_DIR / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    """主入口 - 若存在前端页面则返回，否则返回简单信息页"""
    if (FRONTEND_DIR / "index.html").exists():
        with open(FRONTEND_DIR / "index.html", "r", encoding="utf-8") as f:
            return f.read()
    return f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <title>{settings.APP_NAME} V{settings.APP_VERSION}</title>
    <style>
        body {{font-family:-apple-system,"Microsoft YaHei",sans-serif;max-width:800px;margin:40px auto;padding:0 20px;color:#1f2937}}
        h1 {{color:#2563eb}}
        .card {{background:#f8fafc;border:1px solid #e2e8f0;padding:16px 24px;border-radius:12px;margin-top:20px}}
        code {{background:#eef2ff;padding:2px 6px;border-radius:4px;color:#3730a3}}
        a {{color:#2563eb}}
    </style></head><body>
    <h1>🚀 {settings.APP_NAME} V{settings.APP_VERSION}</h1>
    <p>企业轻量化 AI RAG 知识库 + 自动化工作流 —— 工程级稳定交付版</p>
    <div class="card">
        <h3>核心能力</h3>
        <ul>
            <li>✅ 多格式文档批量导入（PDF/Word/Excel/PPT/TXT/MD/CSV）</li>
            <li>✅ 私有化语义向量库 + RAG 智能问答</li>
            <li>✅ 文档智能摘要 + 要点提取</li>
            <li>✅ 5 套自动化工作流（报表/文案/清洗/通知/批处理）</li>
            <li>✅ 云端密钥 / Ollama 本地模型双模自由切换</li>
            <li>✅ Token 用量统计、限流、操作日志</li>
        </ul>
    </div>
    <div class="card">
        <h3>API 文档</h3>
        <p><a href="/docs" target="_blank">👉 Swagger UI - /docs</a></p>
        <p><a href="/redoc" target="_blank">👉 ReDoc - /redoc</a></p>
    </div>
    <div class="card">
        <h3>运行信息</h3>
        <p>AI 模式：<code>{settings.AI_MODE}</code></p>
        <p>存储目录：<code>{settings.STORAGE_BASE}</code></p>
        <p>向量库：<code>{settings.CHROMA_DIR}</code></p>
    </div>
    <p style="margin-top:40px;color:#6b7280">© 轻企AI智能办公系统 · 企业私有化部署版</p>
    </body></html>
    """


# 挂载 API 路由
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(workflows_router)
app.include_router(system_router)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION,
            "ai_mode": settings.AI_MODE}


# 提供存储文件下载
@app.get("/exports/{path:path}")
async def download_export(path: str):
    file_path = os.path.join(settings.EXPORT_DIR, path)
    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"message": "文件不存在"})
    return FileResponse(file_path, filename=os.path.basename(file_path))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.APP_HOST, port=settings.APP_PORT,
                reload=settings.DEBUG, log_level="info")
