"""
云端密钥大模型 - 适配 OpenAI 兼容协议（如本地代理 / one-api / 三方转发）
"""

from typing import List, Optional
import httpx

from .base import BaseAIProvider as BaseAI
from ..core.config import settings
from ..core.logger import get_logger

logger = get_logger("ai.cloud")


class CloudProvider(BaseAI):
    """云 API 调用。连接失败或端点不可用时返回 None，让上层自行兜底"""

    def __init__(self):
        self.api_key: str = settings.CLOUD_API_KEY
        self.base_url: str = settings.CLOUD_API_BASE.rstrip("/")
        self.model: str = settings.CLOUD_MODEL_NAME
        self.embedding_model: str = settings.CLOUD_EMBEDDING_MODEL
        self.timeout: float = 60.0

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _get_verify(self) -> bool:
        return self.base_url.startswith("https://")

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout, verify=self._get_verify())

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        """
        对话生成。
        - 成功时返回文本
        - API 不可用 / 密钥无效时返回 None（调用方应提供兜底提示）
        """
        if not self.api_key:
            logger.warning("[Cloud] 未配置 CLOUD_API_KEY，跳过云端调用")
            return None

        system_prompt = system_prompt or "你是专业、高效的企业AI助手。"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.TEMPERATURE,
            "max_tokens": max_tokens or settings.MAX_TOKENS,
            "stream": False,
        }
        url = f"{self.base_url}/chat/completions"
        logger.debug(f"[Cloud] 发起请求 model={self.model} base={self.base_url}")

        try:
            with self._client() as client:
                r = client.post(url, json=payload, headers=self._headers())
                r.raise_for_status()
                data = r.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if not content:
                    content = data.get("choices", [{}])[0].get("text") or \
                              data.get("response", "") or \
                              data.get("content", "")
                if not content:
                    logger.warning("[Cloud] 模型未返回有效内容")
                    return None
                tokens = data.get("usage", {}).get("total_tokens", 0)
                logger.info(f"[Cloud] 完成 tokens={tokens}")
                return content.strip()
        except httpx.HTTPStatusError as e:
            logger.warning(f"[Cloud] HTTP 错误 {e.response.status_code}: {e.response.text[:200]}")
            return None
        except Exception as e:
            logger.warning(f"[Cloud] 调用失败（API 可能未启动或不可达）: {e}")
            return None

    def embed(self, texts: List[str]) -> Optional[List[List[float]]]:
        """嵌入 API，失败返回 None"""
        if not self.api_key:
            logger.warning("[Cloud] 未配置 CLOUD_API_KEY，跳过嵌入")
            return None

        url = f"{self.base_url}/embeddings"
        results: List[List[float]] = []

        try:
            with self._client() as client:
                for text in texts:
                    payload = {
                        "model": self.embedding_model,
                        "input": text,
                    }
                    r = client.post(url, json=payload, headers=self._headers())
                    r.raise_for_status()
                    data = r.json()
                    vec = data.get("data", [{}])[0].get("embedding", [])
                    if not vec:
                        logger.warning("[Cloud] 嵌入 API 返回空向量")
                        return None
                    results.append(vec)
            return results
        except httpx.HTTPStatusError as e:
            logger.warning(f"[Cloud] 嵌入 HTTP 错误 {e.response.status_code}，跳过嵌入: {e.response.text[:100]}")
            return None
        except Exception as e:
            logger.warning(f"[Cloud] 嵌入失败，跳过本次嵌入: {e}")
            return None
