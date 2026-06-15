#!/bin/bash
# 轻企AI智能办公系统 V1.0 - macOS / Linux 启动脚本
set -e

echo ""
echo "============================================================"
echo "  轻企AI智能办公系统 V1.0  —— 启动服务 (macOS / Linux)"
echo "============================================================"
echo ""

cd "$(dirname "$0")"

if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到 python3，请先安装 Python 3.10+"
    exit 1
fi

# 创建虚拟环境
if [ ! -d ".venv" ]; then
    echo "[1/3] 创建 Python 虚拟环境 .venv ..."
    python3 -m venv .venv
fi

# 激活
source .venv/bin/activate

echo "[2/3] 安装/更新项目依赖 ..."
python -m pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f ".env" ]; then
    echo "[!] 未检测到 .env，将使用 .env.example 默认配置启动。"
    echo "    如需自定义密钥/Ollama 地址，请复制 .env.example 为 .env 后修改。"
fi

echo ""
echo "[3/3] 启动 FastAPI 服务，地址: http://127.0.0.1:8000"
echo "  - 前端页面: http://127.0.0.1:8000/"
echo "  - API 文档 : http://127.0.0.1:8000/docs"
echo "  - 关闭服务请按 Ctrl + C"
echo ""

cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
