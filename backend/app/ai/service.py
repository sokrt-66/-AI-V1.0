"""
AI 服务入口 - 统一封装云密钥 / Ollama 本地双模式调用
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any
from datetime import date

from .base import BaseAIProvider as BaseAI
from .cloud import CloudProvider
from .ollama_provider import OllamaAIProvider as OllamaProvider
from ..core.config import settings
from ..core.logger import get_logger
from ..core.database import SessionLocal
from ..models import TokenUsage

logger = get_logger("ai.service")

_mode_cache: Dict[str, "BaseAI"] = {}


def get_provider(mode: Optional[str] = None) -> "BaseAI":
    mode = mode or settings.AI_MODE
    if mode not in _mode_cache:
        provider: BaseAI
        if mode == "local":
            provider = OllamaProvider()
        else:
            provider = CloudProvider()
        _mode_cache[mode] = provider
    return _mode_cache[mode]


def reset_cache() -> None:
    _mode_cache.clear()


def _record_tokens(llm: int = 0, embedding: int = 0) -> None:
    """记录当日 Token 使用量（用于限流与统计）"""
    try:
        with SessionLocal() as db:
            row = (
                db.query(TokenUsage)
                .filter(TokenUsage.date == date.today())
                .first()
            )
            if row is None:
                row = TokenUsage(date=date.today(), request_count=1,
                                  llm_tokens=llm, embedding_tokens=embedding,
                                  total_tokens=llm + embedding)
                db.add(row)
            else:
                row.request_count += 1
                row.llm_tokens += llm
                row.embedding_tokens += embedding
                row.total_tokens = row.llm_tokens + row.embedding_tokens
            db.commit()
    except Exception as e:
        logger.debug(f"[AI] Token 用量记录失败（非致命）: {e}")


def chat(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    mode: Optional[str] = None,
) -> str:
    """
    统一的对话生成接口。
    - 若 provider 返回 None（API 不可达 / 密钥无效 / 模型未安装），
      则返回友好的系统提示给用户，而不是抛异常导致整个 API 500。
    """
    provider = get_provider(mode)
    try:
        resp = provider.chat(prompt, system_prompt, temperature, max_tokens)
    except Exception as e:
        logger.error(f"[AI] provider.chat 抛出未预期异常: {e}")
        resp = None

    if not resp:
        mode_name = mode or settings.AI_MODE
        if mode_name == "local":
            return (
                "⚠️ 本地模型未就绪\n\n"
                f"请确认：\n"
                f"1) Ollama 服务是否已启动（默认 http://127.0.0.1:11434）\n"
                f"2) 是否已执行 `ollama pull {settings.OLLAMA_MODEL_NAME}` 下载模型\n"
                f"3) 如切换到云端密钥，请在「系统设置」把模式改为 cloud"
            )
        else:
            return (
                "⚠️ AI 服务暂不可用\n\n"
                f"请确认：\n"
                f"1) 云端 API 服务（{settings.CLOUD_API_BASE}）是否已启动并可访问\n"
                f"2) 配置文件 backend/.env 中的 CLOUD_API_KEY 是否正确\n"
                f"3) 模型名称 {settings.CLOUD_MODEL_NAME} 是否在你的代理中可用\n"
                f"\n提示：如离线使用，可在「系统设置」切换到 local 模式，"
                f"并安装 Ollama + {settings.OLLAMA_MODEL_NAME} 模型。"
            )

    from ..core.utils import count_tokens_rough
    _record_tokens(llm=count_tokens_rough(prompt) + count_tokens_rough(resp))
    return resp


def embed(texts: List[str], mode: Optional[str] = None) -> Optional[List[List[float]]]:
    """
    统一的嵌入接口。返回 None 表示当前不可用，调用方需自行兜底。
    """
    provider = get_provider(mode)
    try:
        vecs = provider.embed(texts)
    except Exception as e:
        logger.warning(f"[AI] provider.embed 抛出未预期异常: {e}")
        vecs = None

    if vecs:
        from ..core.utils import count_tokens_rough
        _record_tokens(embedding=sum(count_tokens_rough(t) for t in texts))
    return vecs


def set_mode(mode: str) -> Dict[str, Any]:
    """切换 AI 模式（cloud / local），无需重启服务器"""
    if mode not in ("cloud", "local"):
        raise ValueError("mode 必须为 'cloud' 或 'local'")

    reset_cache()
    settings.AI_MODE = mode  # 内存生效（进程内）
    logger.info(f"[AI] 切换至 {mode} 模式")

    provider = get_provider(mode)
    model_info = provider.check_available() if hasattr(provider, "check_available") else None
    return {"mode": mode, "info": model_info}


# 与 system.py API 层使用的名称对齐
set_provider_mode = set_mode


def get_daily_stats() -> Dict[str, Any]:
    try:
        with SessionLocal() as db:
            row = db.query(TokenUsage).filter(TokenUsage.date == date.today()).first()
            if row is None:
                return {"date": str(date.today()), "request_count": 0,
                        "llm_tokens": 0, "embedding_tokens": 0, "total_tokens": 0,
                        "daily_limit": settings.TOKEN_DAILY_LIMIT}
            return {"date": str(row.date),
                    "request_count": row.request_count or 0,
                    "llm_tokens": row.llm_tokens or 0,
                    "embedding_tokens": row.embedding_tokens or 0,
                    "total_tokens": row.total_tokens or 0,
                    "daily_limit": settings.TOKEN_DAILY_LIMIT}
    except Exception as e:
        logger.warning(f"[AI] 查询 Token 用量失败: {e}")
        return {"date": str(date.today()), "request_count": 0,
                "llm_tokens": 0, "embedding_tokens": 0, "total_tokens": 0,
                "daily_limit": settings.TOKEN_DAILY_LIMIT}


get_token_stats = get_daily_stats
