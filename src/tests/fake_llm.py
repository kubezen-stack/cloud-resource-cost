import hashlib
import re
from typing import List
import numpy as np


class FakeLLM:
    """Deterministic LLM stand-in: bag-of-words embeddings and scripted answers."""

    model = "fake-chat"
    embedding_model = "fake-embed"
    DIM = 256

    def __init__(self, answers=None):
        self.answers = list(answers or [])
        self.calls = []
        self.embedded = []
        self.closed = False

    @classmethod
    def vector(cls, text: str) -> List[float]:
        vec = np.zeros(cls.DIM)
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % cls.DIM] += 1.0
        return vec.tolist()

    async def embed(self, texts: List[str]) -> List[List[float]]:
        self.embedded.extend(texts)
        return [self.vector(t) for t in texts]

    async def complete_json(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.answers.pop(0)

    async def aclose(self) -> None:
        self.closed = True
