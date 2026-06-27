from __future__ import annotations

import argparse
from pathlib import Path

from retrieval_stage.config import DEFAULT_CONFIG, RetrievalConfig
from retrieval_stage.embeddings import generate_candidate_embeddings
from retrieval_stage.faiss_index import build_faiss_index, search_jd
from retrieval_stage.text_builders import JDTextBuilder


def make_config(args: argparse.Namespace) -> RetrievalConfig:
    return RetrievalConfig(
        model_name=args.model_name,
        embedding_dim=DEFAULT_CONFIG.embedding_dim,
        batch_size=args.batch_size,
        max_seq_length=args.max_seq_length,
        normalize_embeddings=True,
        faiss_index_type=DEFAULT_CONFIG.faiss_index_type,
    )


def cmd_embed_candidates(args: argparse.Namespace) -> None:
    config = make_config(args)
    generate_candidate_embeddings(
        candidates_path=args.candidates,
        out_dir=args.out_dir,
        batch_size=args.batch_size,
        save_text_audit=not args.no_text_audit,
        config=config,
    )


def cmd_build_index(args: argparse.Namespace) -> None:
    artifacts_dir = Path(args.artifacts_dir)
    build_faiss_index(
        embeddings_path=artifacts_dir / "candidate_embeddings.npy",
        index_path=artifacts_dir / "faiss.index",
        config=make_config(args),
    )


def cmd_search(args: argparse.Namespace) -> None:
    results = search_jd(
        jd_file=args.jd_file,
        artifacts_dir=args.artifacts_dir,
        top_k=args.top_k,
        config=make_config(args),
    )
    if args.out_file:
        Path(args.out_file).parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(args.out_file, index=False)
    print(results.to_string(index=False))


def cmd_preview_jd(args: argparse.Namespace) -> None:
    print(JDTextBuilder().build_from_file(args.jd_file))


def add_common_model_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model-name", default=DEFAULT_CONFIG.model_name)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_CONFIG.batch_size)
    parser.add_argument("--max-seq-length", type=int, default=DEFAULT_CONFIG.max_seq_length)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CPU-only candidate semantic retrieval with E5 and FAISS")
    subparsers = parser.add_subparsers(required=True)

    embed_parser = subparsers.add_parser("embed-candidates", help="Generate and save candidate embeddings")
    embed_parser.add_argument("--candidates", required=True, help="Path to candidate JSON or JSONL")
    embed_parser.add_argument("--out-dir", required=True, help="Artifact output directory")
    embed_parser.add_argument("--no-text-audit", action="store_true", help="Skip writing candidate_texts.jsonl")
    add_common_model_args(embed_parser)
    embed_parser.set_defaults(func=cmd_embed_candidates)

    index_parser = subparsers.add_parser("build-index", help="Build FAISS index from saved embeddings")
    index_parser.add_argument("--artifacts-dir", required=True)
    add_common_model_args(index_parser)
    index_parser.set_defaults(func=cmd_build_index)

    search_parser = subparsers.add_parser("search", help="Retrieve top candidates for a JD")
    search_parser.add_argument("--jd-file", required=True)
    search_parser.add_argument("--artifacts-dir", required=True)
    search_parser.add_argument("--top-k", type=int, default=1000)
    search_parser.add_argument("--out-file", help="Optional CSV output path")
    add_common_model_args(search_parser)
    search_parser.set_defaults(func=cmd_search)

    preview_parser = subparsers.add_parser("preview-jd", help="Print the JD text representation")
    preview_parser.add_argument("--jd-file", required=True)
    preview_parser.set_defaults(func=cmd_preview_jd)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()