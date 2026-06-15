"""
5套标准化工作流实现
1. report  - 智能报表自动生成
2. content - 批量文案自动化
3. cleanup - 数据清洗与标准化
4. notify  - 智能通知与提醒流
5. docbatch - 文档批量处理流水线
"""

from __future__ import annotations
import os
import csv
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from ..core.config import settings
from ..core.logger import get_logger
from ..core.utils import ensure_dir, now_str
from ..ai.service import chat as ai_chat
from ..rag.parser import parse_document
from ..rag.chunker import chunk_document
from ..rag.vector_store import get_vector_store

logger = get_logger("wf.workflows")


def _save_output(filename: str, content: str | bytes, subdir: str = "") -> str:
    out_dir = os.path.join(settings.EXPORT_DIR, subdir) if subdir else settings.EXPORT_DIR
    ensure_dir(out_dir)
    out_path = os.path.join(out_dir, filename)
    if isinstance(content, bytes):
        with open(out_path, "wb") as f:
            f.write(content)
    else:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
    return out_path


# =============== 1. 智能报表 ===============
def run_report(params: Dict[str, Any]) -> Dict[str, Any]:
    """基于指定数据源（CSV/文本目录/文档ID）生成业务报告"""
    source: str = params.get("source", "")  # 文件路径
    report_type: str = params.get("report_type", "业务周报")
    audience: str = params.get("audience", "管理层")
    focus_points: List[str] = params.get("focus_points", ["关键数据", "核心结论", "行动建议"])

    data_text = ""
    if source and os.path.exists(source):
        parsed = parse_document(source)
        data_text = parsed.get("content", "")
    else:
        # 扫描导出目录，取最新 csv
        for fn in sorted(os.listdir(settings.EXPORT_DIR), reverse=True):
            p = os.path.join(settings.EXPORT_DIR, fn)
            if fn.lower().endswith(".csv"):
                parsed = parse_document(p)
                data_text = parsed.get("content", "")
                source = p
                break

    if not data_text.strip():
        return {"status": "error", "output": "未找到可生成报表的数据源，请先提供 CSV 或上传文档"}

    data_text = data_text[:8000]
    prompt = (f"请基于以下业务数据，生成一份【{report_type}】，面向对象：{audience}。\n"
              f"重点维度：{', '.join(focus_points)}。\n"
              f"要求：1) 结构化输出 2) 包含：摘要/关键指标/异常分析/行动建议 3) 中文专业简洁。\n\n"
              f"===== 数据 =====\n{data_text}")

    result = ai_chat(prompt=prompt, system_prompt="你是资深企业分析师，擅长输出高质量业务报告。")

    filename = f"report_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    path = _save_output(filename, f"# {report_type}\n\n> 生成时间: {now_str()}\n\n{result}\n", "reports")

    return {"status": "success", "output": path, "report_text": result}


# =============== 2. 批量文案 ===============
def run_content(params: Dict[str, Any]) -> Dict[str, Any]:
    """批量生成营销/公众号/朋友圈文案"""
    topic: str = params.get("topic", "企业产品推广")
    tone: str = params.get("tone", "专业")
    count: int = int(params.get("count", 5))
    channels: List[str] = params.get("channels", ["公众号", "朋友圈", "短视频脚本"])

    prompt = f"""请为以下主题生成 {count} 套不同风格的企业文案：
主题: {topic}
风格/语气: {tone}
适用渠道: {', '.join(channels)}

要求：
1) 每套文案区分：标题、正文、话题标签/CTA
2) 中文表达，有感染力，符合企业形象
3) 每套之间避免重复
请用"== 方案 1 =="等方式清晰分隔每套方案。
"""
    result = ai_chat(prompt=prompt, system_prompt="你是资深企业文案策划专家。")

    filename = f"content_{topic}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    path = _save_output(filename, f"# {topic} 文案方案\n\n> 生成时间: {now_str()}\n\n{result}\n", "contents")

    return {"status": "success", "output": path, "content_text": result}


# =============== 3. 数据清洗与标准化 ===============
def run_cleanup(params: Dict[str, Any]) -> Dict[str, Any]:
    """对上传目录/文件进行数据清洗：去重、填充、统一格式、标准化"""
    source: str = params.get("source", "")
    deduplicate: bool = bool(params.get("deduplicate", True))
    fill_empty: str = params.get("fill_empty", "N/A")
    normalize_case: str = params.get("normalize_case", "")  # upper/lower/
    date_format: str = params.get("date_format", "%Y-%m-%d")

    files = []
    if source and os.path.exists(source):
        if os.path.isdir(source):
            for fn in os.listdir(source):
                if fn.lower().endswith((".csv", ".txt")):
                    files.append(os.path.join(source, fn))
        else:
            files.append(source)
    else:
        # 默认扫描上传目录
        for fn in os.listdir(settings.UPLOAD_DIR):
            if fn.lower().endswith((".csv", ".txt")):
                files.append(os.path.join(settings.UPLOAD_DIR, fn))

    if not files:
        return {"status": "error", "output": "未发现可清洗的数据文件（.csv/.txt）"}

    outputs = []
    total_rows = 0
    cleaned_rows = 0
    for f in files:
        try:
            with open(f, "r", encoding="utf-8-sig", errors="ignore") as fp:
                lines = fp.readlines()
        except Exception:
            continue

        if f.lower().endswith(".csv"):
            reader = csv.reader(lines)
            out_lines: List[str] = []
            seen = set()
            header = None
            for idx, row in enumerate(reader):
                if not row:
                    continue
                if header is None:
                    header = row
                    out_lines.append(",".join([f'"{c}"' for c in row]))
                    continue
                # 去重
                row_key = "||".join(row)
                if deduplicate and row_key in seen:
                    continue
                seen.add(row_key)
                # 填充空值
                row = [c.strip() if c.strip() else fill_empty for c in row]
                # 大小写
                if normalize_case == "upper":
                    row = [c.upper() for c in row]
                elif normalize_case == "lower":
                    row = [c.lower() for c in row]
                out_lines.append(",".join([f'"{c}"' for c in row]))
                cleaned_rows += 1
                total_rows += 1
            out_name = "cleaned_" + os.path.basename(f)
            path = _save_output(out_name, "\n".join(out_lines), "cleanup")
            outputs.append(path)
        else:
            cleaned = []
            seen = set()
            for line in lines:
                s = line.strip()
                if not s:
                    continue
                if deduplicate and s in seen:
                    continue
                seen.add(s)
                if normalize_case == "upper":
                    s = s.upper()
                elif normalize_case == "lower":
                    s = s.lower()
                cleaned.append(s)
                cleaned_rows += 1
                total_rows += 1
            out_name = "cleaned_" + os.path.basename(f)
            path = _save_output(out_name, "\n".join(cleaned), "cleanup")
            outputs.append(path)

    return {
        "status": "success",
        "output": outputs,
        "files": len(files),
        "total_rows": total_rows,
        "cleaned_rows": cleaned_rows,
    }


# =============== 4. 智能通知与提醒 ===============
def run_notify(params: Dict[str, Any]) -> Dict[str, Any]:
    """生成提醒通知内容（邮件/消息/日程），输出到文件"""
    notify_type: str = params.get("notify_type", "会议提醒")
    recipients: List[str] = params.get("recipients", ["全体员工"])
    topic: str = params.get("topic", "季度业务会议")
    when: str = params.get("when", datetime.now().strftime("%Y-%m-%d 14:00"))
    extra: str = params.get("extra", "")

    prompt = f"""请帮我生成一份【{notify_type}】通知：
- 收件人: {', '.join(recipients)}
- 主题: {topic}
- 时间: {when}
- 附加信息: {extra or '无'}

要求：中文、正式、清晰、包含 主题/时间/地点/议程/行动项 五要素。"""

    result = ai_chat(prompt=prompt, system_prompt="你是资深行政/运营通知撰写助手。")

    filename = f"notify_{notify_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    path = _save_output(filename, f"主题: {topic}\n时间: {when}\n收件人: {', '.join(recipients)}\n\n{result}\n", "notifications")

    return {"status": "success", "output": path, "notify_text": result}


# =============== 5. 文档批量处理 ===============
def run_docbatch(params: Dict[str, Any]) -> Dict[str, Any]:
    """批量处理文档：解析 + 切片 + 向量化 + 摘要，输出汇总"""
    source_dir: str = params.get("source_dir", settings.UPLOAD_DIR)
    action: str = params.get("action", "parse+summary")  # parse / parse+vector / parse+summary

    os.makedirs(source_dir, exist_ok=True)
    files = []
    for fn in os.listdir(source_dir):
        p = os.path.join(source_dir, fn)
        if os.path.isfile(p) and not fn.startswith("."):
            files.append(p)
    if not files:
        return {"status": "error", "output": f"目录 {source_dir} 下没有可处理的文档"}

    results = []
    vs = get_vector_store() if "vector" in action else None

    for idx, f in enumerate(files, 1):
        try:
            parsed = parse_document(f)
            summary = ""
            if "summary" in action and parsed["content"]:
                prompt = f"请为以下文档生成100-200字中文摘要：\n\n{parsed['content'][:4000]}"
                summary = ai_chat(prompt=prompt, system_prompt="你是专业文档摘要助手。", temperature=0.2)

            chunked = []
            if "vector" in action and parsed["content"]:
                chunked = chunk_document(parsed["content"])
                vs.add_chunks(-1, os.path.basename(f), chunked)

            results.append({
                "file": os.path.basename(f),
                "size": parsed["file_size"],
                "chars": parsed["content_length"],
                "chunks": len(chunked),
                "summary": (summary or "")[:200],
            })
            logger.info(f"[DocBatch] {idx}/{len(files)} 处理: {os.path.basename(f)}")
        except Exception as e:
            results.append({"file": os.path.basename(f), "error": str(e)})

    report_lines = [f"# 文档批量处理报告", f"> 生成时间: {now_str()}", f"> 处理数量: {len(results)}", ""]
    for r in results:
        if "error" in r:
            report_lines.append(f"- ❌ {r['file']}: {r['error']}")
        else:
            report_lines.append(f"- ✅ {r['file']} | 字数:{r['chars']} | 切片:{r['chunks']} | 摘要: {r['summary']}")

    filename = f"docbatch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    path = _save_output(filename, "\n".join(report_lines), "docbatch")
    return {"status": "success", "output": path, "files": results}


WORKFLOW_REGISTRY = {
    "report": run_report,
    "content": run_content,
    "cleanup": run_cleanup,
    "notify": run_notify,
    "docbatch": run_docbatch,
}


def run_workflow_by_type(wf_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    fn = WORKFLOW_REGISTRY.get(wf_type)
    if not fn:
        return {"status": "error", "output": f"未知的工作流类型: {wf_type}"}
    try:
        return fn(params or {})
    except Exception as e:
        logger.exception(f"工作流 {wf_type} 异常: {e}")
        return {"status": "error", "output": str(e)}
