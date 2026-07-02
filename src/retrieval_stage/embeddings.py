from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from .config import DEFAULT_CONFIG, RetrievalConfig
from .io_utils import count_candidate_records, iter_candidate_records, save_candidate_ids
from .text_builders import CandidateTextBuilder


class E5Embedder:
    def __init__(self, config: RetrievalConfig = DEFAULT_CONFIG) -> None:
        self.config = config
        self.model = SentenceTransformer(config.model_name, device="cpu")
        self.model.max_seq_length = config.max_seq_length

    def encode_passages(self, texts: Sequence[str], batch_size: int | None = None) -> np.ndarray:
        return self._encode([f"passage: {text}" for text in texts], batch_size=batch_size)

    def encode_query(self, text: str) -> np.ndarray:
        embedding = self._encode([f"query: {text}"], batch_size=1)
        return embedding[0]

    def _encode(self, texts: Sequence[str], batch_size: int | None = None) -> np.ndarray:
        embeddings = self.model.encode(
            list(texts),
            batch_size=batch_size or self.config.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=self.config.normalize_embeddings,
            show_progress_bar=False,
        )
        return np.asarray(embeddings, dtype=np.float32)


def batched(items: Iterable[tuple[str, str]], batch_size: int) -> Iterable[list[tuple[str, str]]]:
    batch: list[tuple[str, str]] = []
    for item in items:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def generate_candidate_embeddings(
    candidates_path: str | Path,
    out_dir: str | Path,
    batch_size: int = DEFAULT_CONFIG.batch_size,
    save_text_audit: bool = True,
    config: RetrievalConfig = DEFAULT_CONFIG,
) -> None:
    candidates_path = Path(candidates_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    total = count_candidate_records(candidates_path)
    embeddings_path = out_dir / "candidate_embeddings.npy"
    ids_path = out_dir / "candidate_ids.csv"
    metadata_path = out_dir / "metadata.json"
    text_audit_path = out_dir / "candidate_texts.jsonl"

    embeddings = np.lib.format.open_memmap(
        embeddings_path,
        mode="w+",
        dtype=np.float32,
        shape=(total, config.embedding_dim),
    )

    text_builder = CandidateTextBuilder()
    embedder = E5Embedder(config)
    candidate_ids: list[str] = []
    cursor = 0

    audit_handle = text_audit_path.open("w", encoding="utf-8") if save_text_audit else None
    try:
        id_text_iter = (
            (str(candidate["candidate_id"]), text_builder.build(candidate))
            for candidate in iter_candidate_records(candidates_path)
        )
        progress = tqdm(total=total, desc="Embedding candidates", unit="candidate")
        for batch in batched(id_text_iter, batch_size):
            batch_ids = [candidate_id for candidate_id, _ in batch]
            batch_texts = [text for _, text in batch]
            batch_embeddings = embedder.encode_passages(batch_texts, batch_size=batch_size)

            next_cursor = cursor + len(batch)
            embeddings[cursor:next_cursor] = batch_embeddings
            cursor = next_cursor
            candidate_ids.extend(batch_ids)

            if audit_handle is not None:
                for candidate_id, text in batch:
                    audit_handle.write(json.dumps({"candidate_id": candidate_id, "text": text}, ensure_ascii=False) + "\n")

            progress.update(len(batch))
        progress.close()
    finally:
        if audit_handle is not None:
            audit_handle.close()

    embeddings.flush()
    save_candidate_ids(candidate_ids, ids_path)

    metadata = {
        "model_name": config.model_name,
        "embedding_dim": config.embedding_dim,
        "num_candidates": total,
        "normalized": config.normalize_embeddings,
        "faiss_index_type": config.faiss_index_type,
        "batch_size": batch_size,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")