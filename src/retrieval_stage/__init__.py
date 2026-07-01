"""CPU-only candidate embedding and retrieval stage."""

__all__ = [
    "CandidateTextBuilder",
    "JDTextBuilder",
]

from retrieval_stage.text_builders import CandidateTextBuilder, JDTextBuilder