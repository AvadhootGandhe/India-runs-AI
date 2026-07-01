from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalConfig:
    model_name: str = "intfloat/e5-small-v2"
    embedding_dim: int = 384
    batch_size: int = 64
    max_seq_length: int = 512
    normalize_embeddings: bool = True
    faiss_index_type: str = "IndexFlatIP"


DEFAULT_CONFIG = RetrievalConfig()