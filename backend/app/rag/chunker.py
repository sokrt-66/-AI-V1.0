"""
智能文本切片模块：按段落+字数阈值切分，兼顾语义完整
"""

import re
from typing import List, Dict
from ..core.config import settings


def _split_by_paragraph(text: str) -> List[str]:
    """按段落/换行分段"""
    paras = re.split(r"\n\s*\n|\n{2,}", text)
    paras = [p.strip() for p in paras if p.strip()]
    return paras


def chunk_document(text: str, chunk_size: int = None, chunk_overlap: int = None) -> List[Dict]:
    """
    智能切片：
    1. 先按段落拆分
    2. 段落若超出 chunk_size 则按句号/分号再切
    3. 相邻两段之间保留 chunk_overlap 字符的重叠
    """
    chunk_size = chunk_size or settings.CHUNK_SIZE
    chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    paras = _split_by_paragraph(text)
    chunks: List[Dict] = []
    buf = ""

    def flush(buf: str, chunks: List[Dict], overlap: int) -> str:
        if len(buf) <= chunk_size:
            return buf
        # 按标点进一步切
        sub_parts = re.split(r"(?<=[。！？!?;；\.])\s*", buf)
        sub_buf = ""
        for sp in sub_parts:
            if len(sub_buf) + len(sp) <= chunk_size:
                sub_buf += sp
            else:
                if sub_buf.strip():
                    chunks.append({"text": sub_buf.strip(), "index": len(chunks)})
                # 保留 overlap
                sub_buf = sub_buf[-overlap:] + sp if len(sub_buf) > overlap else sp
        return sub_buf

    for p in paras:
        if len(buf) + len(p) <= chunk_size:
            buf += ("\n" if buf else "") + p
        else:
            if buf.strip():
                chunks.append({"text": buf.strip(), "index": len(chunks)})
            buf = p[-chunk_overlap:] + "\n" + p if len(buf) > chunk_overlap else p

    if buf.strip():
        chunks.append({"text": buf.strip(), "index": len(chunks)})

    # 兜底：强制再切一次超长块
    final = []
    for c in chunks:
        t = c["text"]
        if len(t) <= chunk_size:
            final.append({"text": t, "index": len(final)})
        else:
            # 按字符数硬切
            for i in range(0, len(t), chunk_size - chunk_overlap):
                piece = t[i:i + chunk_size].strip()
                if piece:
                    final.append({"text": piece, "index": len(final)})
    return final
