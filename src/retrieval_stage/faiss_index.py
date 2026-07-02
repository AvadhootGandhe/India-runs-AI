from __future__ import annotations

from pathlib import Path

import faiss
import numpy as np
import pandas as pd

from .config import DEFAULT_CONFIG, RetrievalConfig
from .embeddings import E5Embedder
from .io_utils import load_candidate_ids
from .text_builders import JDTextBuilder


def build_faiss_index(
    embeddings_path: str | Path,
    index_path: str | Path,
    config: RetrievalConfig = DEFAULT_CONFIG,
) -> None:
    embeddings = np.load(embeddings_path, mmap_mode="r")
    if embeddings.shape[1] != config.embedding_dim:
        raise ValueError(f"Expected embedding dim {config.embedding_dim}, got {embeddings.shape[1]}")

    index = faiss.IndexFlatIP(config.embedding_dim)
    index.add(np.asarray(embeddings, dtype=np.float32))
    faiss.write_index(index, str(index_path))


def search_jd(
    jd_file: str | Path,
    artifacts_dir: str | Path,
    top_k: int = 1000,
    config: RetrievalConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    artifacts_dir = Path(artifacts_dir)
    index_path = artifacts_dir / "faiss.index"
    ids_path = artifacts_dir / "candidate_ids.csv"

    index = faiss.read_index(str(index_path))
    candidate_ids = load_candidate_ids(ids_path)

    jd_text = JDTextBuilder().build_from_file(jd_file)
    query_embedding = E5Embedder(config).encode_query(jd_text).reshape(1, -1)

    safe_top_k = min(top_k, len(candidate_ids))
    scores, positions = index.search(query_embedding.astype(np.float32), safe_top_k)

    rows = []
    for rank, (score, position) in enumerate(zip(scores[0], positions[0]), start=1):
        if position < 0:
            continue
        rows.append(
            {
                "rank": rank,
                "candidate_id": candidate_ids[int(position)],
                "score": float(score),
            }
        )
    return pd.DataFrame(rows)