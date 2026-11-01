"""Thin LLM client. The advisor depends on the LLMClient protocol only, so the
provider can be swapped in one place (see get_llm_client)."""
import logging
from typing import List, Optional, Protocol
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """The LLM provider failed or returned something unusable."""


class LLMNotConfigured(LLMError):
    """No API key / unsupported provider: the advisor cannot run."""


class LLMClient(Protocol):
    model: str
    embedding_model: str

    async def complete_json(self, system: str, user: str) -> str:
        """Return the model answer as a JSON string."""

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Return one embedding vector per input text, in order."""

    async def aclose(self) -> None:
        """Release network resources."""


class OpenAICompatibleClient:
    """Chat completions + embeddings over the OpenAI REST API (and compatible servers)."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        embedding_model: str,
        timeout: float = 60.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.model = model
        self.embedding_model = embedding_model
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )

    async def _post(self, path: str, payload: dict) -> dict:
        try:
            response = await self._client.post(path, json=payload)
        except httpx.HTTPError as e:
            logger.exception("LLM request to %s failed", path)
            raise LLMError(f"LLM provider unreachable: {type(e).__name__}") from e
        if response.status_code >= 400:
            # The body may echo the prompt, so only the status is logged/raised.
            logger.error("LLM provider returned HTTP %s for %s", response.status_code, path)
            raise LLMError(f"LLM provider returned HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as e:
            raise LLMError("LLM provider returned invalid JSON") from e

    async def complete_json(self, system: str, user: str) -> str:
        data = await self._post("/chat/completions", {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        })
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError("Unexpected chat completion response") from e

    async def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        data = await self._post("/embeddings", {"model": self.embedding_model, "input": texts})
        try:
            items = sorted(data["data"], key=lambda item: item["index"])
            vectors = [item["embedding"] for item in items]
        except (KeyError, TypeError) as e:
            raise LLMError("Unexpected embeddings response") from e
        if len(vectors) != len(texts):
            raise LLMError("Embeddings count does not match the input")
        return vectors

    async def aclose(self) -> None:
        await self._client.aclose()


def get_llm_client() -> LLMClient:
    if not settings.LLM_API_KEY:
        raise LLMNotConfigured("LLM_API_KEY is not set")
    if settings.LLM_PROVIDER != "openai":
        raise LLMNotConfigured(f"Unsupported LLM provider: {settings.LLM_PROVIDER}")
    return OpenAICompatibleClient(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        embedding_model=settings.EMBEDDING_MODEL,
        timeout=settings.LLM_TIMEOUT_SECONDS,
    )
