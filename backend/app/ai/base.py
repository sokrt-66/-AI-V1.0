"""
AI 模型统一接口：
- chat(prompt, system_prompt) -> str
- embed(texts) -> list[list[float]]

通过 settings.AI_MODE 切换 cloud / local
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional

from ..core.config import settings
from ..core.logger import get_logger

logger = get_logger("ai.base")


class BaseAIProvider:
    """AI 服务基础类"""
    name: str = "base"

    def embed(self, texts: List[str]) -> Optional[List[List[float]]]:
        """返回嵌入向量列表；返回 None 表示当前不可用"""
        return None

    def chat(self, prompt: str, system_prompt: Optional[str] = None,
             temperature: Optional[float] = None,
             max_tokens: Optional[int] = None) -> str:
        raise NotImplementedError


# 引入具体实现
