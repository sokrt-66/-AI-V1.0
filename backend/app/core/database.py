"""
SQLite 数据库连接与 ORM 基础
包含：自动建表 + 增量 schema 升级 + 连接管理
"""

import os
from pathlib import Path
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import settings, ensure_dirs

ensure_dirs()

DATABASE_URL = f"sqlite:///{settings.DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """依赖注入：数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _column_sql(col) -> str:
    """把 SQLAlchemy Column 转成 SQL 列定义字符串"""
    col_type = col.type.compile(dialect=engine.dialect)
    parts = [f"{col.name} {col_type}"]
    if not col.nullable and not col.primary_key:
        parts.append("NOT NULL")
    if col.default is not None and hasattr(col.default, "arg"):
        val = col.default.arg
        if isinstance(val, str):
            parts.append(f"DEFAULT '{val}'")
        elif val is not None:
            parts.append(f"DEFAULT {val}")
    return " ".join(parts)


def _migrate_schema() -> None:
    """
    增量 schema 升级 - 对比现有表和代码模型
    发现缺失的表：CREATE TABLE
    发现缺失的列：ALTER TABLE ADD COLUMN
    安全、幂等，对新旧数据库都能兼容
    """
    engine.dispose()  # 强制刷新连接，避免 inspect 缓存
    from sqlalchemy import text as _sql

    # 用原生 SQLite PRAGMA 拿到真实的现有列名（最可靠）
    with engine.connect() as conn:
        result = conn.execute(_sql("SELECT name FROM sqlite_master WHERE type='table'"))
        existing_tables = {row[0] for row in result.fetchall()}

    from .. import models as _  # noqa: F401

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            try:
                table.create(engine)
            except Exception:
                continue

        # 用 PRAGMA 获取真实的列名
        try:
            with engine.connect() as conn:
                result = conn.execute(_sql(f"PRAGMA table_info({table_name})"))
                existing_cols = {row[1] for row in result.fetchall()}
        except Exception:
            continue

        for col in table.columns:
            if col.name in existing_cols or col.primary_key:
                continue
            sql = f"ALTER TABLE {table_name} ADD COLUMN {_column_sql(col)}"
            try:
                with engine.connect() as conn:
                    conn.execute(_sql(sql))
                    conn.commit()
            except Exception:
                pass


def init_db() -> None:
    """
    初始化数据库表 - 先建表，再做增量 schema 升级
    """
    from .. import models as _  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _migrate_schema()
