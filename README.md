# 🚀 轻企AI智能办公系统 V1.0
## 企业轻量化 AI RAG 知识库 + 自动化工作流 —— 工程级稳定交付版

面向中小微企业，解决两大刚需：
1. **企业资料无法智能问答**（合同、产品、培训、售后资料沉睡）
2. **每日重复办公工作耗人**（报表、汇总、整理、对账、文案）

---

## 一、技术栈

| 模块 | 选型 | 说明 |
| --- | --- | --- |
| **后端** | Python 3.10+ / FastAPI | 高性能异步 API（41个接口） |
| **前端** | Vue 3 + Element Plus (CDN) | 零构建、开箱即用 |
| **向量库** | ChromaDB (本地文件) | 零运维、完全私有化 |
| **数据库** | SQLite | 单文件、零安装（12张表，支持增量 schema 迁移） |
| **文档解析** | PyPDF2 / python-docx / openpyxl / python-pptx | 主流办公格式全覆盖 |
| **任务调度** | APScheduler | cron 表达式定时触发 |
| **AI 模型** | 云端密钥 (OpenAI 风格) **+** Ollama 本地开源 | 双模自由切换 |

---

## 二、一分钟极速启动

### Windows 用户
```bash
# 双击执行或在 PowerShell/CMD 中执行
start.bat
```

### macOS / Linux 用户
```bash
chmod +x start.sh
./start.sh
```

### 启动完成后打开浏览器访问
- 前端控制台：http://127.0.0.1:8000/
- Swagger API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

> 💡 首次执行会自动创建虚拟环境 `.venv` 并安装依赖，耗时约 1-3 分钟。

---

## 三、目录结构

```
RAG/
├── start.bat                    # Windows 一键启动
├── start.sh                     # Mac/Linux 一键启动
├── README.md                    # 本文
├── backend/                     # 后端核心
│   ├── main.py                  # FastAPI 入口
│   ├── requirements.txt         # Python 依赖（含 psutil）
│   ├── .env                     # 实际运行配置（已配置企业密钥）
│   ├── .env.example             # 配置示例
│   ├── app/
│   │   ├── core/                # 配置 / 数据库（自动迁移）/ 工具函数 / 日志
│   │   ├── ai/                  # 云端 + Ollama 双模型调用层
│   │   ├── rag/                 # 文档解析 + 切片 + 向量库 + 问答 + 会话管理
│   │   ├── workflow/            # 5 套工作流 + APScheduler 调度
│   │   ├── service/             # 运营分析 + 健康监控 + 告警系统
│   │   ├── api/                 # FastAPI 路由（6 个子模块）
│   │   ├── schemas/             # 请求/响应 Pydantic 模型
│   │   └── models.py            # SQLAlchemy ORM 模型（12张表）
│   └── storage/                 # 运行时产生（上传文件/向量库/数据库/日志）
│       ├── chroma/              # 向量索引 (ChromaDB)
│       ├── uploads/             # 上传的原始文件
│       ├── exports/             # 工作流输出文件（报表/文案...）
│       └── logs/                # 应用日志
└── frontend/                    # 前端（单文件，无需构建）
    └── index.html               # Vue3 + Element Plus CDN 版控制台（深色主题）
```

---

## 四、核心功能

### 📚 模块一：私有 RAG 智能知识库系统
1. **多格式文档批量导入** —— PDF / DOCX / XLSX / PPTX / TXT / MD / CSV
2. **自动文档清洗 + 智能切片** —— 按段落 + 字数阈值切分，保证语义完整
3. **私有化语义向量库** —— ChromaDB 本地存储，数据完全不出企业
4. **智能问答对话** —— RAG 检索增强生成，答案附参考资料来源与相关度
5. **文档摘要 + 要点提取** —— 为每个文档生成结构化摘要
6. **多会话管理** —— 支持会话命名、收藏、归档、导出（Markdown/JSON/HTML）

### ⚙️ 模块二：AI 自动化工作流引擎（5 套标准工作流）

| 类型 | 用途 | 参数示例 |
| --- | --- | --- |
| `report` | 智能报表自动生成 | `{"report_type":"周报", "focus_points":["关键指标","核心结论"]}` |
| `content` | 批量文案自动化 | `{"topic":"产品推广", "tone":"专业", "count": 5}` |
| `cleanup` | 数据清洗与标准化 | `{"deduplicate": true, "fill_empty": "N/A"}` |
| `notify` | 智能通知与提醒 | `{"topic":"季度会议", "when":"2025-12-01 09:00"}` |
| `docbatch` | 文档批量处理流水线 | `{"action":"parse+summary+vector"}` |

所有工作流支持：
- **cron 定时调度**（例如 `0 9 * * *` 每天早上 9 点自动执行）
- **手动触发** —— 一键立即执行
- **执行历史记录** —— 每次运行状态、耗时、输出持久化

### 🧠 模块三：AI 双模型调用方案

| 方案 | 适用场景 | 优势 |
| --- | --- | --- |
| ☁️ **云端密钥**（默认） | 常规企业商用 | 零算力成本、模型效果优、部署极简 |
| 🖥️ **Ollama 本地模型** | 涉密/金融/政务/离线 | 数据绝对安全、无外部依赖、完全自主可控 |

在 `系统设置` 页 **一键切换**，无需重启服务、无需改代码。

### 📊 模块四：运营分析与仪表盘
- **实时仪表盘** —— 文档数/向量切片/对话次数/工作流运行统计
- **Token 用量趋势** —— 折线图展示近 7/14/30 天用量
- **功能使用统计** —— 按功能维度的使用量追踪
- **系统健康监控** —— CPU/内存/磁盘使用率实时显示

### 🔔 模块五：告警与审计
- **系统告警** —— 自动检测异常并记录
- **操作审计日志** —— 所有操作可追溯、可审计
- **健康状态指示灯** —— 顶栏实时显示系统状态（绿/黄/红）

---

## 五、配置文件说明 (`backend/.env`)

当前已配置企业密钥，可直接运行：

```dotenv
# AI 模式: cloud / local
AI_MODE=cloud

# ===== 云端密钥方案（已配置企业密钥）=====
CLOUD_API_KEY=sk-0FZx7yc8vhLicPSMY1a5jnBUhkUyeqB2k8Je5er4DZQAizhG
CLOUD_API_BASE=https://api.tupo.ai/v1
CLOUD_MODEL_NAME=DeepSeek-V4-Flash
CLOUD_EMBEDDING_MODEL=text-embedding-3-small

# ===== Ollama 本地方案（AI_MODE=local 时生效） =====
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL_NAME=qwen2.5:7b
OLLAMA_EMBEDDING_MODEL=bge-m3

# ===== RAG 参数 =====
CHUNK_SIZE=500
CHUNK_OVERLAP=80
TOP_K=6
TEMPERATURE=0.3
MAX_TOKENS=2048

# ===== Token 限流 =====
TOKEN_DAILY_LIMIT=10000000
ENABLE_TOKEN_STATS=true

# ===== 服务端口 =====
APP_PORT=8000
DEBUG=true
```

---

## 六、Ollama 本地模型部署（可选）

> 仅在选择 **local 模式** 时需要，如使用云端密钥可跳过此节。

```bash
# 1. 安装 Ollama
#    macOS / Windows: https://ollama.com/download
#    Linux:
curl -fsSL https://ollama.com/install.sh | sh

# 2. 下载企业中文模型（推荐 qwen2.5:7b，约 4.5GB）
ollama pull qwen2.5:7b

# 3. 下载嵌入模型（用于向量检索）
ollama pull bge-m3

# 4. 验证服务
curl http://127.0.0.1:11434/api/tags
# 应返回包含 qwen2.5:7b 与 bge-m3 的模型列表
```

推荐硬件配置：
- **最低**：16GB 内存 + 现代多核 CPU（速度较慢，可跑）
- **推荐**：32GB 内存 + RTX 3090 / 4080 及以上 GPU（CUDA 加速）
- **生产**：64GB 内存 + RTX 4090 / A10 / L4

---

## 七、常见问题

### Q1. 启动后前端页面打不开？
A. 确认 `backend/storage/` 目录已创建，浏览器访问 `http://127.0.0.1:8000/`。若仍异常，查看控制台日志或访问 `/health` 检查健康状态。

### Q2. 云端模式提示调用失败？
A. 检查 `.env` 中 `CLOUD_API_KEY` 与 `CLOUD_API_BASE` 是否正确；当前已配置 `https://api.tupo.ai/v1` 与企业密钥。

### Q3. Ollama 本地模式失败？
A. ① 确认 `ollama serve` 正常运行；② 检查 `http://127.0.0.1:11434/api/tags` 能返回模型列表；③ 下载对应模型 `ollama pull qwen2.5:7b`。

### Q4. 中文回答质量不理想？
A. ① 在 `系统设置` 中调大 `Top-K`（4-8）；② 降低 `Temperature`（0.1-0.3）；③ 增加企业文档数量与质量，保证文档覆盖问题领域。

### Q5. 如何备份与迁移？
A. 直接拷贝整个 `backend/storage/` 目录即可（包含向量库、数据库、上传文件与导出结果）。

### Q6. 嵌入模型提示 403 错误？
A. 当前嵌入模型 `text-embedding-3-small` 需要额外权限，系统会自动降级为 BM25 关键词检索，不影响问答功能使用。

---

## 八、API 快速参考

| 方法 | 路径 | 功能 |
| --- | --- | --- |
| POST | `/api/documents/upload` | 上传并处理文档 |
| GET | `/api/documents` | 文档列表（支持搜索/分页/分类） |
| GET | `/api/documents/{id}` | 文档详情（摘要+要点+预览） |
| DELETE | `/api/documents/{id}` | 删除文档与向量 |
| POST | `/api/chat` | 智能问答（RAG 检索增强） |
| GET | `/api/chat/history` | 问答历史 |
| POST | `/api/chat/sessions` | 创建新会话 |
| GET | `/api/chat/sessions` | 会话列表（支持收藏/归档） |
| POST | `/api/chat/export` | 导出会话（Markdown/JSON/HTML） |
| POST | `/api/workflows` | 新建工作流 |
| GET | `/api/workflows` | 工作流列表 |
| POST | `/api/workflows/run` | 立即执行工作流 |
| GET | `/api/workflows/{id}/runs` | 工作流执行记录 |
| GET | `/api/system/dashboard/stats` | 仪表盘统计数据 |
| GET | `/api/system/dashboard/token-trend` | Token 用量趋势 |
| GET | `/api/system/health` | 系统健康状态 |
| GET | `/api/system/alerts` | 告警列表 |
| GET | `/api/system/logs` | 操作审计日志 |
| GET | `/api/system/settings` | 获取系统配置 |
| PATCH | `/api/system/settings` | 更新运行时配置 |

完整接口文档：http://127.0.0.1:8000/docs

---

## 九、商业交付版本对应

| 套餐 | 对应功能 | 典型场景 |
| --- | --- | --- |
| **基础版（5000元）** | 单一自动化工作流系统 | 企业某一项重复任务自动化（如每日报表） |
| **标准版（12800元）** | 完整私有 RAG 知识库系统 | 合同查询、培训问答、制度检索、产品资料检索 |
| **企业版（29800元）** | RAG + 工作流全套 + 权限/日志/调优 + 源码 + 运维 | 企业级综合办公 AI 平台 |

---

## 十、工程规范与扩展指南

### 新增一套工作流
1. 在 `backend/app/workflow/workflows.py` 中实现 `run_xxx(params)` 函数
2. 在底部 `WORKFLOW_REGISTRY` 字典中注册类型名
3. 前端无需修改，`工作流` 页会自动识别

### 接入新的 AI 模型
1. 在 `backend/app/ai/` 目录下创建 `xxx_provider.py`，继承基础调用接口
2. 在 `service.py` 中按模式切换即可复用

### 自定义向量/切片策略
修改 `backend/app/rag/chunker.py`（切片逻辑）、`vector_store.py`（向量存储/检索）。

---

## 十一、当前配置验证状态

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| 服务启动 | ✅ | 41 个接口全部就绪 |
| AI 模型 | ✅ | DeepSeek-V4-Flash @ api.tupo.ai |
| 数据库 | ✅ | 12 张表，支持增量迁移 |
| 前端控制台 | ✅ | Vue3 + 深色主题 + 仪表盘 |
| 工作流引擎 | ✅ | 5 套内置工作流 + APScheduler |

**启动命令**: `start.bat` → http://127.0.0.1:8000

---

**© 轻企AI智能办公系统 · 企业私有化部署版 · 源码交付 · 零年费**
