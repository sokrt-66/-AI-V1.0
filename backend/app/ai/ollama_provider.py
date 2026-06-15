"""
Ollama 本地开源模型调用
"""

import json
import httpx
from typing import List, Optional

from .base import BaseAIProvider
from ..core.config import settings
from ..core.logger import get_logger

logger = get_logger("ai.ollama")


class OllamaAIProvider(BaseAIProvider):
    name = "local"

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.OLLAMA_MODEL_NAME
        self.embedding_model = settings.OLLAMA_EMBEDDING_MODEL
        self.timeout = 300.0

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt or "你是专业、专业、高效的企业AI助手。",
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else settings.TEMPERATURE,
            },
        }
        logger.debug(f"[Ollama] 发起请求 model={self.model}")
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(url, json=payload)
                r.raise_for_status()
                data = r.json()
                content = data.get("response", "")
                eval_count = data.get("eval_count", 0)
                logger.info(f"[Ollama] 完成 eval_count={eval_count}")
                return content.strip()
        except Exception as e:
            logger.error(f"[Ollama] 调用失败: {e}")
            raise RuntimeError(f"本地模型调用失败，请确认 Ollama 服务是否正常运行: {e}")

    def embed(self, texts: List[str]) -> List[List[float]]:
        url = f"{self.base_url}/api/embed"
        results = []
        try:
            with httpx.Client(timeout=self.timeout) as client:
                for text in texts:
                    payload = {"model": self.embedding_model, "input": text}
                    r = client.post(url, json=payload)
                    r.raise_for_status()
                    data = r.json()
                    vec = (data.get("embeddings") or [[0.0] * 128])[0]
                    results.append(vec)
            return results
        except Exception as e:
            logger.error(f"[Ollama] 嵌入失败: {e}")
            raise
