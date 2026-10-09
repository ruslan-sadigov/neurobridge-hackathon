"""Embedding adapter. `local` = multilingual sentence-transformers model; `hash` = offline stub for tests."""
from __future__ import annotations

import hashlib
import re
from typing import Protocol

import numpy as np

from ..config import get_settings


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> np.ndarray: ...  # L2-normalised, shape (n, d)


class HashingEmbedder:
    """Deterministic bag-of-words hashing. No model download; good enough for tests and offline fallback."""

    def __init__(self, dim: int = 512):
        self.dim = dim

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in re.findall(r"\w+", t.lower()):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                out[i, h % self.dim] += 1.0 if (h >> 8) & 1 else -1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.where(norms == 0, 1, norms)


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # heavy: install separately

        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self._model.encode(texts, normalize_embeddings=True), dtype=np.float32)


_cached: Embedder | None = None


def get_embedder() -> Embedder:
    global _cached
    if _cached is None:
        s = get_settings()
        _cached = HashingEmbedder() if s.embedding_backend == "hash" else SentenceTransformerEmbedder(s.embedding_model)
    return _cached
