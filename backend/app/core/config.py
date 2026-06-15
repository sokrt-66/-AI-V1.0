"""
全局配置管理 - 轻企AI智能办公系统 V1.0
支持从 .env 文件读取配置；存储路径（STORAGE_BASE/DB_PATH 等）始终相对项目。
"""

import os
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


# 项目目录（backend/ 目录，即 app 的父目录）
# __file__ = .../backend/app/core/config.py
# parent.parent = .../backend/app (Python package root)
# parent.parent.parent = .../backend  (项目后端根)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_STORAGE = str(BASE_DIR / "storage")
PROJECT_DB = str(BASE_DIR / "storage" / "app.db")
PROJECT_UPLOADS = str(BASE_DIR / "storage" / "uploads")
PROJECT_EXPORTS = str(BASE_DIR / "storage" / "exports")
PROJECT_LOGS = str(BASE_DIR / "storage" / "logs")
PROJECT_CHROMA = str(BASE_DIR / "storage" / "chroma")


# 优先查找 backend/.env，其次 backend/.env.example
_env_file = BASE_DIR / ".env"
if not _env_file.exists():
    _env_file = BASE_DIR / ".env.example"


class Settings(BaseSettings):
    """运行时配置（AI_MODE、API_KEY、模型等），不覆盖硬编码的存储路径"""

    model_config = SettingsConfigDict(
        env_file=_env_file,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "Light-Enterprise AI Office System"
    APP_VERSION: str = "1.0.0"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True

    # AI 模式：cloud（云端密钥）/ local（Ollama）
    AI_MODE: str = "cloud"

    # 云端密钥配置
    CLOUD_API_KEY: str = ""
    CLOUD_API_BASE: str = "http://localhost:3000"
    CLOUD_MODEL_NAME: str = "gpt-4o-mini"
    CLOUD_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Ollama 本地配置
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL_NAME: str = "qwen2.5:7b"
    OLLAMA_EMBEDDING_MODEL: str = "bge-m3"

    # RAG 参数
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 80
    TOP_K: int = 6
    TEMPERATURE: float = 0.3
    MAX_TOKENS: int = 2048

    # Token 统计
    TOKEN_DAILY_LIMIT: int = 10_000_000
    ENABLE_TOKEN_STATS: bool = True

    # ------------ 存储路径（硬编码，避免被系统环境变量覆盖） ------------
    STORAGE_BASE: str = PROJECT_STORAGE
    UPLOAD_DIR: str = PROJECT_UPLOADS
    EXPORT_DIR: str = PROJECT_EXPORTS
    LOG_DIR: str = PROJECT_LOGS
    DB_PATH: str = PROJECT_DB
    CHROMA_DIR: str = PROJECT_CHROMA

    def model_post_init(self, __context) -> None:
        """强制执行：存储路径始终相对本项目 backend 目录，不受外部环境变量干扰"""
        object.__setattr__(self, "STORAGE_BASE", PROJECT_STORAGE)
        object.__setattr__(self, "UPLOAD_DIR", PROJECT_UPLOADS)
        object.__setattr__(self, "EXPORT_DIR", PROJECT_EXPORTS)
        object.__setattr__(self, "LOG_DIR", PROJECT_LOGS)
        object.__setattr__(self, "DB_PATH", PROJECT_DB)
        object.__setattr__(self, "CHROMA_DIR", PROJECT_CHROMA)


@lru_cache
def get_settings() -> Settings:
    """获取单例配置对象"""
    return Settings()


settings = get_settings()


def ensure_dirs() -> None:
    """确保所有存储目录存在"""
    for d in [settings.STORAGE_BASE, settings.UPLOAD_DIR,
              settings.EXPORT_DIR, settings.LOG_DIR, settings.CHROMA_DIR]:
        os.makedirs(d, exist_ok=True)
