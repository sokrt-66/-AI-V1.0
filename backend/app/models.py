"""
SQLAlchemy 模型定义 - 完整商业版
包含：文档管理、RAG对话、工作流调度、运营分析、审计日志
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

from .core.database import Base


# ============================================================
# 文档知识库
# ============================================================

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, default=0)
    file_type = Column(String(32), default="")
    content_length = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    category = Column(String(64), default="默认")
    tags = Column(String(512), default="")       # 逗号分隔多标签
    status = Column(String(32), default="pending")  # pending / parsing / done / error
    summary = Column(Text, default="")
    key_points = Column(Text, default="")         # JSON 格式要点列表
    storage_path = Column(String(512), default="")
    language = Column(String(16), default="zh")    # 文档语言
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class DocumentTag(Base):
    """文档标签（多对多）"""
    __tablename__ = "document_tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), unique=True, nullable=False)
    color = Column(String(16), default="#1890ff")  # 标签颜色
    count = Column(Integer, default=0)             # 引用次数
    created_at = Column(DateTime, default=datetime.now)


# ============================================================
# RAG 智能问答
# ============================================================

class ChatSession(Base):
    """对话会话 - 支持重命名、收藏、导出"""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(128), default="新对话")      # 自动生成或用户命名
    model = Column(String(64), default="")            # 使用的模型
    message_count = Column(Integer, default=0)        # 消息轮次
    token_usage = Column(Integer, default=0)          # 本会话累计 token
    is_favorite = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    tags = Column(String(256), default="")           # 会话标签
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ChatLog(Base):
    """问答对话记录"""
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), index=True, default="default")
    question = Column(Text, default="")
    answer = Column(Text, default="")
    sources = Column(JSON, default=list)              # RAG 检索来源
    source_count = Column(Integer, default=0)         # 来源文档数
    tokens_used = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)           # 响应耗时（毫秒）
    model = Column(String(64), default="")           # 调用的模型
    search_mode = Column(String(32), default="vector")  # vector / keyword / hybrid
    created_at = Column(DateTime, default=datetime.now)


class PromptTemplate(Base):
    """提示词模板库"""
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    description = Column(String(512), default="")
    system_prompt = Column(Text, default="")
    user_prompt_template = Column(Text, default="")  # 支持 {{variable}} 占位符
    category = Column(String(64), default="通用")
    icon = Column(String(32), default="📝")
    is_default = Column(Boolean, default=False)
    use_count = Column(Integer, default=0)            # 被调用次数
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ============================================================
# 自动化工作流引擎
# ============================================================

class Workflow(Base):
    """工作流定义"""
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(512), default="")
    type = Column(String(64), nullable=False)         # report / content / cleanup / notify / docbatch / webhook
    cron = Column(String(64), default="")            # Linux cron 表达式
    params = Column(JSON, default=dict)               # 工作流参数
    enabled = Column(Boolean, default=True)
    webhook_url = Column(String(512), default="")    # Webhook 触发地址
    webhook_secret = Column(String(128), default="")  # Webhook 签名密钥
    notify_on_success = Column(Boolean, default=False)
    notify_on_failure = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)    # 下次执行时间
    last_status = Column(String(32), default="idle")  # idle / running / success / failed
    last_duration_ms = Column(Integer, default=0)
    total_runs = Column(Integer, default=0)
    success_runs = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class WorkflowRun(Base):
    """工作流执行记录"""
    __tablename__ = "workflow_runs"
    __table_args__ = (
        UniqueConstraint("workflow_id", "run_index", name="uq_wf_run_index"),
    )

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, index=True)
    run_index = Column(Integer, default=1)            # 第 N 次执行
    status = Column(String(32), default="running")   # running / success / failed / cancelled
    trigger = Column(String(32), default="manual")    # manual / scheduled / webhook
    started_at = Column(DateTime, default=datetime.now)
    finished_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, default=0)
    output = Column(Text, default="")
    output_file = Column(String(512), default="")    # 生成的报告文件路径
    detail = Column(JSON, default=dict)              # 详细执行数据
    error_message = Column(Text, default="")          # 失败时的错误信息
    created_at = Column(DateTime, default=datetime.now)


# ============================================================
# 运营分析与统计
# ============================================================

class TokenUsage(Base):
    """每日 Token 用量统计"""
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(16), index=True)
    embedding_tokens = Column(Integer, default=0)
    llm_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    request_count = Column(Integer, default=0)
    avg_latency_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)


class FeatureUsage(Base):
    """功能使用量统计（按功能维度）"""
    __tablename__ = "feature_usage"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(16), index=True)
    feature = Column(String(64), index=True)         # rag_chat / doc_upload / workflow_run / summarize
    count = Column(Integer, default=0)
    tokens = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)


class SystemHealth(Base):
    """系统健康状态记录"""
    __tablename__ = "system_health"

    id = Column(Integer, primary_key=True, index=True)
    metric = Column(String(64), nullable=False)       # uptime / cpu / memory / disk / api_latency
    value = Column(Float, default=0)
    status = Column(String(16), default="ok")        # ok / warning / critical
    detail = Column(Text, default="")
    recorded_at = Column(DateTime, default=datetime.now)


# ============================================================
# 审计与操作日志
# ==========================================================

class OpLog(Base):
    """操作审计日志"""
    __tablename__ = "op_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(64), default="")
    target = Column(String(255), default="")
    target_id = Column(Integer, nullable=True)
    status = Column(String(32), default="ok")         # ok / failed
    detail = Column(Text, default="")
    ip_address = Column(String(64), default="")
    user_agent = Column(String(256), default="")
    created_at = Column(DateTime, default=datetime.now)


class Alert(Base):
    """系统告警"""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    level = Column(String(16), default="info")         # info / warning / error / critical
    source = Column(String(64), default="")
    title = Column(String(256), default="")
    message = Column(Text, default="")
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
