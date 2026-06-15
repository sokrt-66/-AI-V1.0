"""
向量数据库 + 关键词检索双重引擎
- 优先使用 ChromaDB 向量语义检索
- 若嵌入 API 不可用，自动降级为关键词匹配（TF-IDF 权重）
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
import uuid
import re
import math
from collections import Counter

from ..core.config import settings
from ..core.logger import get_logger

logger = get_logger("rag.vector")


# ============================================================
# 关键词检索兜底（嵌入 API 不可用时）
# ============================================================

def _tokenize(text: str) -> List[str]:
    """
    中文文本分词：提取 2-4 字滑动窗口 n-gram（捕获词语/短语/专有名词）。
    英文提取为独立词（保留原始大小写以增加区分度）。
    """
    ngrams: List[str] = []
    # 提取英文词（保留大小写区分度高）
    en = re.findall(r"[a-zA-Z]{2,}", text)
    ngrams.extend(en)
    # 提取 2-4 字滑动窗口 n-gram
    cn = re.findall(r"[\u4e00-\u9fff]+", text)
    for chunk in cn:
        chunk_len = len(chunk)
        for n in range(2, 5):  # 2-4 字词
            for i in range(chunk_len - n + 1):
                ngrams.append(chunk[i:i + n])
    return ngrams


def _bm25_score(query: str, texts: List[str], k1: float = 1.5, b: float = 0.75) -> List[float]:
    """简化的 BM25 算法，用于无嵌入 API 时的关键词检索"""
    q_terms = _tokenize(query)
    if not q_terms:
        return [0.0] * len(texts)

    doc_tokens = [_tokenize(t) for t in texts]
    n = len(doc_tokens)
    avg_dl = sum(len(t) for t in doc_tokens) / max(n, 1)

    doc_freq = Counter()
    for tokens in doc_tokens:
        for t in set(tokens):
            doc_freq[t] += 1

    scores = []
    for tokens in doc_tokens:
        score = 0.0
        dl = len(tokens)
        tf = Counter(tokens)
        for q in q_terms:
            if q in tf:
                tf_val = tf[q]
                df = max(doc_freq[q], 1)
                idf = math.log((n - df + 0.5) / (df + 0.5) + 1)
                score += idf * (tf_val * (k1 + 1)) / (tf_val + k1 * (1 - b + b * dl / max(avg_dl, 1)))
        scores.append(score)
    return scores


def keyword_search(query: str, chunks: List[Dict], top_k: int) -> List[Dict]:
    """关键词 BM25 兜底检索"""
    texts = [c.get("text", "") for c in chunks]
    scores = _bm25_score(query, texts)
    max_score = max(scores) if scores else 1.0
    scored = sorted(zip(scores, chunks), key=lambda x: x[0], reverse=True)
    results = []
    for raw, chunk in scored[:top_k]:
        norm = raw / max_score if max_score > 0 else 0.0
        results.append({
            "text": chunk.get("text", ""),
            "document_id": chunk.get("document_id"),
            "title": chunk.get("title", ""),
            "chunk_index": chunk.get("chunk_index", 0),
            "score": round(norm, 4),
        })
    return results


# ============================================================
# ChromaDB 向量存储
# ============================================================

class VectorStore:
    """
    向量存储封装：
    - 优先向量语义检索
    - 嵌入 API 不可用时降级为 BM25 关键词检索
    """

    def __init__(self, persist_dir: Optional[str] = None):
        self.persist_dir = persist_dir or settings.CHROMA_DIR
        from ..core.utils import ensure_dir
        ensure_dir(self.persist_dir)
        self._client = None
        self._collection = None
        self._embed_available = True  # 标记嵌入 API 是否可用

    @property
    def client(self):
        if self._client is None:
            import chromadb
            self._client = chromadb.PersistentClient(path=self.persist_dir)
        return self._client

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name="enterprise_kb",
                metadata={"description": "企业知识库向量索引"},
            )
        return self._collection

    def _embed(self, texts: List[str]) -> Optional[List[List[float]]]:
        """调用嵌入 API，失败返回 None"""
        try:
            from ..ai.service import embed as ai_embed
            return ai_embed(texts)
        except Exception as e:
            if self._embed_available:
                logger.warning(f"[Vector] 嵌入 API 不可用，降级为关键词检索: {e}")
                self._embed_available = False
            return None

    def add_chunks(self, document_id: int, title: str, chunks: List[Dict]) -> int:
        """写入切片到向量库"""
        if not chunks:
            return 0

        texts = [c["text"] for c in chunks]

        if self._embed_available:
            try:
                vecs = self._embed(texts)
            except Exception as e:
                logger.warning(f"[Vector] 写入时嵌入失败，降级存储文本（仅支持关键词检索）: {e}")
                vecs = None
        else:
            vecs = None

        ids = [f"d{document_id}_{uuid.uuid4().hex}" for _ in texts]
        metas = [
            {
                "document_id": document_id,
                "title": title,
                "chunk_index": i,
                "source": title,
                "text": t[:200],  # 保留文本摘要便于关键词检索
            }
            for i, t in enumerate(texts)
        ]

        try:
            if vecs:
                self.collection.add(ids=ids, embeddings=vecs, documents=texts, metadatas=metas)
            else:
                self.collection.add(ids=ids, documents=texts, metadatas=metas)
            logger.info(f"[Vector] 已写入 {len(texts)} 切片（向量模式={'是' if vecs else '否'}）")
            return len(texts)
        except Exception as e:
            logger.error(f"[Vector] ChromaDB 写入失败: {e}")
            return 0

    def search(self, query: str, top_k: Optional[int] = None,
               document_ids: Optional[List[int]] = None) -> List[Dict]:
        """
        检索策略：
        1. 嵌入 API 可用 → ChromaDB 向量语义检索
        2. 嵌入 API 不可用 → 全量 chunks 按 BM25 关键词匹配
        """
        top_k = top_k or settings.TOP_K

        if self._embed_available:
            try:
                [vec] = self._embed([query])
            except Exception as e:
                logger.warning(f"[Vector] 嵌入查询失败，降级为关键词检索: {e}")
                self._embed_available = False
                return self._keyword_fallback(query, top_k, document_ids)

            where = None
            if document_ids:
                where = {"document_id": {"$in": document_ids}}

            result = self.collection.query(
                query_embeddings=[vec],
                n_results=top_k,
                where=where,
            )

            docs = result.get("documents", [[]])[0]
            metas = result.get("metadatas", [[]])[0]
            dists = result.get("distances", [[]])[0]

            if not docs:
                return []

            items = []
            for doc, meta, dist in zip(docs, metas, dists):
                score = max(0.0, 1.0 - float(dist))
                items.append({
                    "text": doc,
                    "document_id": meta.get("document_id"),
                    "title": meta.get("title", ""),
                    "chunk_index": meta.get("chunk_index", 0),
                    "score": round(score, 4),
                })
            items.sort(key=lambda x: x["score"], reverse=True)
            return items
        else:
            return self._keyword_fallback(query, top_k, document_ids)

    def _keyword_fallback(self, query: str, top_k: int,
                         document_ids: Optional[List[int]]) -> List[Dict]:
        """BM25 关键词兜底检索"""
        try:
            all_items = self.collection.get(include=["documents", "metadatas"])
            rows = []
            for i, (doc, meta) in enumerate(zip(all_items.get("documents", []),
                                                 all_items.get("metadatas", []))):
                if document_ids and meta.get("document_id") not in document_ids:
                    continue
                rows.append({"text": doc, **meta})
            results = keyword_search(query, rows, top_k)
            logger.info(f"[Vector] BM25 关键词检索命中 {len(results)} 条")
            return results
        except Exception as e:
            logger.warning(f"[Vector] 关键词检索也失败: {e}")
            return []

    def delete_by_document(self, document_id: int) -> int:
        """根据文档ID删除其所有向量"""
        data = self.collection.get(
            where={"document_id": {"$eq": document_id}},
            include=[],
        )
        ids = data.get("ids", [])
        if ids:
            self.collection.delete(ids=ids)
        return len(ids)

    def get_stats(self) -> Dict:
        cnt = self.collection.count()
        return {"total_chunks": cnt, "embed_mode": "vector" if self._embed_available else "keyword"}


_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
