"""
Pydantic Schema - 完整商业版 API 契约
包含：通用、文档管理、RAG问答、工作流、统计、系统设置
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================================
# 通用
# ============================================================

class ApiResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Optional[Any] = None


class Pagination(BaseModel):
    page: int = 1
    page_size: int = 20


# ============================================================
# 文档知识库
# ============================================================

class DocumentIn(BaseModel):
    title: str = ""
    category: str = "默认"
    tags: str = ""          # 逗号分隔多标签


class DocumentOut(BaseModel):
    id: int
    title: str
    file_name: str
    file_size: int
    file_type: str
    content_length: int
    chunk_count: int
    category: str
    tags: str = ""
    status: str
    summary: str = ""
    key_points: str = ""
    language: str = "zh"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentBatchIn(BaseModel):
    """批量文档上传"""
    files: List[Dict[str, Any]]  # [{title, category, tags}]
    default_category: str = "默认"
    default_tags: str = ""


class DocumentTagIn(BaseModel):
    name: str
    color: str = "#1890ff"


class DocumentTagOut(BaseModel):
    id: int
    name: str
    color: str
    count: int = 0

    class Config:
        from_attributes = True


# ============================================================
# RAG 智能问答
# ============================================================

class ChatRequest(BaseModel):
    question: str = Field(..., description="用户问题")
    session_id: str = "default"
    top_k: Optional[int] = None
    temperature: Optional[float] = None
    use_rag: bool = True
    document_ids: Optional[List[int]] = None  # 指定检索的文档范围
    template_id: Optional[int] = None          # 使用提示词模板


class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]] = []
    tokens_used: int = 0
    latency_ms: int = 0
    mode: str = "cloud"
    model: str = ""
    search_mode: str = "vector"
    session_id: str = ""


class StreamChatRequest(ChatRequest):
    """流式问答（与普通问答共用响应格式，前端 SSE 接收）"""
    stream: bool = True


class SessionOut(BaseModel):
    """会话列表项"""
    session_id: str
    title: str
    model: str = ""
    message_count: int = 0
    token_usage: int = 0
    is_favorite: bool = False
    is_archived: bool = False
    tags: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class SessionUpdate(BaseModel):
    """更新会话元信息"""
    title: Optional[str] = None
    is_favorite: Optional[bool] = None
    is_archived: Optional[bool] = None
    tags: Optional[str] = None


class ChatExportRequest(BaseModel):
    """对话导出请求"""
    session_id: str
    format: str = "markdown"  # markdown / json / html / pdf
    include_sources: bool = True
    include_metadata: bool = True


class ChatExportResponse(BaseModel):
    """导出结果"""
    file_path: str
    file_name: str
    size: int
    format: str


class SummaryRequest(BaseModel):
    document_id: Optional[int] = None
    text: Optional[str] = None
    max_length: int = 300


class KeyPointsRequest(BaseModel):
    document_id: Optional[int] = None
    text: Optional[str] = None
    k: int = 5


class PromptTemplateIn(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""
    user_prompt_template: str = ""
    category: str = "通用"
    icon: str = "📝"
    is_default: bool = False


class PromptTemplateOut(BaseModel):
    id: int
    name: str
    description: str
    system_prompt: str
    user_prompt_template: str
    category: str
    icon: str
    is_default: bool
    use_count: int = 0
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


# ============================================================
# 自动化工作流
# ============================================================

class WorkflowIn(BaseModel):
    name: str
    description: str = ""
    type: str = "report"   # report/content/cleanup/notify/docbatch/webhook
    cron: str = ""          # Linux cron: "0 9 * * 1-5" = 每个工作日9点
    params: Dict[str, Any] = {}
    enabled: bool = True
    webhook_url: str = ""
    webhook_secret: str = ""
    notify_on_success: bool = False
    notify_on_failure: bool = True


class WorkflowOut(BaseModel):
    id: int
    name: str
    description: str
    type: str
    cron: str
    enabled: bool
    webhook_url: str
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    last_status: str
    last_duration_ms: int = 0
    total_runs: int = 0
    success_runs: int = 0
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class WorkflowRunRequest(BaseModel):
    workflow_id: int
    params: Dict[str, Any] = {}
    trigger: str = "manual"


class WorkflowRunOut(BaseModel):
    id: int
    workflow_id: int
    run_index: int
    status: str
    trigger: str
    duration_ms: int = 0
    output: str = ""
    output_file: str = ""
    error_message: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    class Config:
        from_attributes = True


class WebhookTrigger(BaseModel):
    """外部 Webhook 触发工作流"""
    workflow_id: int
    payload: Dict[str, Any] = {}
    signature: str = ""     # HMAC-SHA256 签名验证


# ============================================================
# 运营分析与统计
# ============================================================

class TokenStatsResponse(BaseModel):
    date: str
    llm_tokens: int = 0
    embedding_tokens: int = 0
    total_tokens: int = 0
    request_count: int = 0
    avg_latency_ms: int = 0
    daily_limit: int = 10_000_000
    usage_percent: float = 0.0


class FeatureUsageResponse(BaseModel):
    feature: str
    count: int = 0
    tokens: int = 0


class DashboardStats(BaseModel):
    """仪表盘统计数据"""
    doc_count: int = 0
    chunk_count: int = 0
    session_count: int = 0
    chat_count: int = 0
    workflow_count: int = 0
    workflow_runs_today: int = 0
    token_today: int = 0
    token_daily_limit: int = 10_000_000
    api_latency_ms: int = 0
    uptime_seconds: float = 0.0


class TokenTrend(BaseModel):
    """Token 使用趋势（折线图数据）"""
    dates: List[str]
    llm_tokens: List[int]
    embedding_tokens: List[int]
    request_counts: List[int]


class FeatureTrend(BaseModel):
    """功能使用趋势（柱状图数据）"""
    dates: List[str]
    features: Dict[str, List[int]]  # {feature: [count per day]}


# ============================================================
# 系统管理与健康
# ============================================================

class HealthResponse(BaseModel):
    """系统健康状态"""
    status: str = "ok"     # ok / warning / critical
    uptime_seconds: float = 0.0
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    api_latency_ms: int = 0
    db_connected: bool = True
    vector_connected: bool = True
    ai_available: bool = False


class AlertIn(BaseModel):
    title: str
    message: str = ""
    level: str = "info"   # info / warning / error / critical


class AlertOut(BaseModel):
    id: int
    level: str
    source: str
    title: str
    message: str
    is_resolved: bool
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class SettingsUpdate(BaseModel):
    ai_mode: Optional[str] = None
    temperature: Optional[float] = None
    top_k: Optional[int] = None
    chunk_size: Optional[int] = None
    max_tokens: Optional[int] = None


class OpLogFilter(BaseModel):
    action: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    page: int = 1
    page_size: int = 50
