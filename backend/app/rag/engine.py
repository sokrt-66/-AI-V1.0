"""
RAG 问答引擎 - 整合检索+生成（全链路容错：API 不可达时不崩溃）
"""

from typing import List, Dict, Any, Optional

from .vector_store import get_vector_store
from ..ai.service import chat as ai_chat
from ..core.config import settings
from ..core.logger import get_logger
from ..core.database import SessionLocal
from ..models import ChatLog

logger = get_logger("rag.engine")


RAG_SYSTEM_PROMPT = """你是专业的企业知识库AI助手。
必须严格按照下面提供的"参考资料"回答用户问题：
1. 只能基于参考资料中的事实作答，禁止编造资料中没有的信息；
2. 如果参考资料无法回答问题，明确告知用户"暂未收录相关内容，请补充资料后再试"；
3. 回答要求：中文、结构化、简洁、要点清晰；
4. 关键信息可适当引用原文片段，用引号标注。
"""


def _build_prompt(question: str, sources: List[Dict]) -> str:
    refs = []
    for idx, s in enumerate(sources, 1):
        refs.append(f"【参考资料 {idx}】\n标题: {s.get('title')}\n内容: {s.get('text')}\n相关度: {s.get('score')}")
    ref_block = "\n\n".join(refs) if refs else "（无参考资料）"
    return f"===== 用户问题 =====\n{question}\n\n===== 参考资料 =====\n{ref_block}\n\n===== 请回答 =====\n"


def _looks_like_error(text: str) -> bool:
    """简易判断：是否为系统故障提示（不是模型正常生成内容）"""
    markers = ["AI 服务暂不可用", "本地模型未就绪", "⚠️", "由于目标计算机积极拒绝"]
    return any(m in text for m in markers)


def answer(
    question: str,
    session_id: str = "default",
    top_k: Optional[int] = None,
    temperature: Optional[float] = None,
    use_rag: bool = True,
    document_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """RAG 问答主流程 - 全链路容错"""
    question = (question or "").strip()
    if not question:
        return {"answer": "请您输入问题后重试。", "sources": [], "tokens_used": 0, "mode": settings.AI_MODE}

    sources = []
    if use_rag:
        try:
            vs = get_vector_store()
            sources = vs.search(question, top_k=top_k or settings.TOP_K, document_ids=document_ids)
            logger.info(f"[RAG] 检索到 {len(sources)} 条相关切片")
        except Exception as e:
            logger.warning(f"[RAG] 检索失败: {e}")
            sources = []

    if use_rag and sources:
        prompt = _build_prompt(question, sources)
        system = RAG_SYSTEM_PROMPT
    else:
        prompt = question
        system = "你是专业的企业AI助手，用中文简洁回答。"

    try:
        answer_text = ai_chat(
            prompt=prompt,
            system_prompt=system,
            temperature=temperature if temperature is not None else settings.TEMPERATURE,
        )
    except Exception as e:
        logger.error(f"[RAG] 生成失败: {e}")
        answer_text = "⚠️ AI 服务暂不可用，请稍后重试。"

    from ..core.utils import count_tokens_rough
    tokens = count_tokens_rough(prompt) + count_tokens_rough(answer_text)

    # 持久化问答日志（含丰富元数据）
    search_mode = "vector" if (sources and use_rag) else ("keyword" if sources else "none")
    try:
        with SessionLocal() as db:
            db.add(ChatLog(
                session_id=session_id,
                question=question,
                answer=answer_text,
                sources=sources[:10],
                source_count=len(sources),
                tokens_used=tokens,
                latency_ms=0,
                model=settings.CLOUD_MODEL_NAME,
                search_mode=search_mode,
            ))
            db.commit()
    except Exception as e:
        logger.warning(f"问答日志写入失败: {e}")

    return {
        "answer": answer_text,
        "sources": sources[:10],
        "tokens_used": tokens,
        "mode": settings.AI_MODE,
    }


def summarize(text: str, max_len: int = 500) -> str:
    """长文本摘要 - API 不可用时返回空字符串（避免把故障信息当摘要）"""
    if not text or len(text) <= max_len:
        return text[:max_len] if text else ""

    prompt = f"请为以下企业文档生成一份不超过300字的中文摘要，要求：\n- 涵盖核心要点\n- 突出重点内容\n- 语言精炼、专业\n\n===== 文档内容 =====\n{text[:6000]}"
    try:
        result = ai_chat(prompt=prompt, system_prompt="你是专业的企业文档总结助手。", temperature=0.2)
        if _looks_like_error(result):
            return text[:max_len]
        return result or text[:max_len]
    except Exception as e:
        logger.warning(f"摘要生成失败，退化为截断: {e}")
        return text[:max_len]


def extract_key_points(text: str, k: int = 5) -> List[str]:
    """文档要点提取 - API 不可用时返回空列表"""
    if not text:
        return []
    prompt = f"请从以下文档中提取不超过 {k} 条核心要点，每条用'●'开头，中文输出：\n\n{text[:4000]}"
    try:
        result = ai_chat(prompt=prompt, system_prompt="你是专业的文档要点提取助手。", temperature=0.2)
        if _looks_like_error(result):
            return []
        points = [p.lstrip("●-• \t").strip() for p in result.splitlines() if p.strip()]
        return points[:k]
    except Exception as e:
        logger.warning(f"要点提取失败: {e}")
        return []
