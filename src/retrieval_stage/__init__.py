"""CPU-only candidate embedding and retrieval stage."""

__all__ = [
    "CandidateTextBuilder",
    "JDTextBuilder",
]

from .text_builders import CandidateTextBuilder, JDTextBuilder