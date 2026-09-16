from typing import Optional

import numpy as np
from openai import OpenAI

from app.config import settings

_client: Optional[OpenAI] = None
EMBEDDING_MODEL = "text-embedding-3-small"


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def get_embedding(text: str) -> list[float]:
    client = _get_client()
    resp = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return resp.data[0].embedding


def batch_get_embeddings(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = _get_client()
    resp = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    sorted_by_index = sorted(resp.data, key=lambda x: x.index)
    return [item.embedding for item in sorted_by_index]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    A = np.array(a, dtype=np.float64)
    B = np.array(b, dtype=np.float64)
    norm = np.linalg.norm(A) * np.linalg.norm(B)
    if norm == 0:
        return 0.0
    return float(np.dot(A, B) / norm)
