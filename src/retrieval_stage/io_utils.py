from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import pandas as pd


def iter_candidate_records(path: str | Path) -> Iterator[dict[str, Any]]:
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".jsonl":
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON on line {line_number} in {path}") from exc
        return

    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            yield from payload
            return
        if isinstance(payload, dict) and isinstance(payload.get("candidates"), list):
            yield from payload["candidates"]
            return
        if isinstance(payload, dict) and "candidate_id" in payload:
            yield payload
            return
        raise ValueError("JSON candidate input must be a candidate object, list, or object with a candidates list")

    raise ValueError(f"Unsupported candidate file type: {path.suffix}")


def count_candidate_records(path: str | Path) -> int:
    return sum(1 for _ in iter_candidate_records(path))


def save_candidate_ids(candidate_ids: list[str], path: str | Path) -> None:
    pd.DataFrame({"candidate_id": candidate_ids}).to_csv(path, index=False)


def load_candidate_ids(path: str | Path) -> list[str]:
    return pd.read_csv(path)["candidate_id"].astype(str).tolist()


def write_jsonl(path: str | Path, rows: Iterator[dict[str, Any]]) -> None:
    with Path(path).open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")