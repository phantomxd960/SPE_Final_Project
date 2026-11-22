"""Text embeddings behind one small interface.

* `fastembed`: BGE-small (ONNX, 384 dimensions), baked into the images.
* `mock`: deterministic feature hashing of words. No model download and no
  network, so CI tests are repeatable; related texts still score higher than
  unrelated ones, which keeps search and graph tests meaningful.
"""

import hashlib
import math
import re
import threading
from functools import lru_cache
from typing import Protocol

from regdiff_common.config import get_settings
from regdiff_common.models import EMBEDDING_DIM

_WORD = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an and are as at be by for from has have in is it its of on or that the this to was were will with".split()
)


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class MockEmbedder:
    name = "mock-hashing"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    @staticmethod
    def _embed_one(text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIM
        for word in _WORD.findall(text.lower()):
            if word in _STOPWORDS:
                continue
            digest = hashlib.md5(word.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIM
            vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


class FastEmbedder:
    def __init__(self, model_name: str, cache_dir: str, threads: int | None = None) -> None:
        from fastembed import TextEmbedding  # imported lazily: optional dependency

        self.name = model_name
        self._model = TextEmbedding(model_name=model_name, cache_dir=cache_dir, threads=threads)
        # One inference at a time per process: concurrent runs each allocate their own
        # working memory and get a pod OOM-killed under load. More load means more pods (HPA).
        self._lock = threading.Lock()

    def embed(self, texts: list[str]) -> list[list[float]]:
        with self._lock:
            return [vector.tolist() for vector in self._model.embed(texts)]


@lru_cache
def get_embedder() -> Embedder:
    settings = get_settings()
    if settings.embeddings_mode == "fastembed":
        return FastEmbedder(settings.embedding_model, settings.model_cache_dir, settings.embedding_threads)
    return MockEmbedder()


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def warm_model_cache() -> None:
    """Download the embedding model at image build time (`python -m regdiff_common.embeddings`)."""
    settings = get_settings()
    FastEmbedder(settings.embedding_model, settings.model_cache_dir).embed(["warm-up"])


if __name__ == "__main__":
    warm_model_cache()
