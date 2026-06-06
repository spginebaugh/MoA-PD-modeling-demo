"""Small data-defined scoring helpers for edge-patch prediction."""

from __future__ import annotations

from dataclasses import dataclass

from services.domain import EdgePatchCandidate


@dataclass(frozen=True)
class ScoredPatch:
    patch: EdgePatchCandidate
    score: float
    model_score: float
    feature_summary: tuple[str, ...]

    def to_candidate(self) -> EdgePatchCandidate:
        return self.patch.model_copy(
            update={
                "score": min(max(self.score, 0.0), 1.0),
                "feature_summary": self.feature_summary,
            }
        )
