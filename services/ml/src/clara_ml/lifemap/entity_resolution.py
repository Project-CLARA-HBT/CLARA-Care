"""Governed Vietnamese entity-resolution candidate ensemble."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

MatchSource = Literal["exact", "alias", "dense"]
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalize_vietnamese(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold().replace("đ", "d"))
    ascii_text = "".join(
        character for character in folded if not unicodedata.combining(character)
    )
    return " ".join(_TOKEN_RE.findall(ascii_text))


@dataclass(frozen=True)
class TerminologyEntry:
    code: str
    display: str
    aliases: tuple[str, ...]
    system: str
    mapping_revision: str
    active: bool = True


@dataclass(frozen=True)
class DenseCandidate:
    code: str
    similarity: float


@dataclass(frozen=True)
class ResolvedCandidate:
    code: str
    display: str
    system: str
    mapping_revision: str
    source: MatchSource
    confidence: float
    rerank_score: float | None

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "display": self.display,
            "system": self.system,
            "mapping_revision": self.mapping_revision,
            "source": self.source,
            "confidence": self.confidence,
            "rerank_score": self.rerank_score,
        }


@dataclass(frozen=True)
class ResolutionResult:
    normalized_text: str
    candidates: tuple[ResolvedCandidate, ...]
    status: Literal["resolved", "ambiguous", "unmapped"]
    policy_version: str = "entity-resolution-v1"

    @property
    def auto_confirmable(self) -> bool:
        return False

    def as_dict(self) -> dict[str, object]:
        return {
            "normalized_text": self.normalized_text,
            "candidates": [candidate.as_dict() for candidate in self.candidates],
            "status": self.status,
            "auto_confirmable": False,
            "policy_version": self.policy_version,
        }


def _calibrate_dense(similarity: float) -> float:
    bounded = max(-1.0, min(1.0, similarity))
    return 1 / (1 + math.exp(-8 * (bounded - 0.72)))


def resolve_entity(
    text: str,
    *,
    terminology: tuple[TerminologyEntry, ...],
    dense_candidates: tuple[DenseCandidate, ...] = (),
    graph_allowed_codes: frozenset[str] | None = None,
    rerank_scores: dict[str, float] | None = None,
    top_k: int = 5,
) -> ResolutionResult:
    normalized = normalize_vietnamese(text)
    if not normalized:
        return ResolutionResult("", (), "unmapped")
    by_code = {entry.code: entry for entry in terminology if entry.active}
    merged: dict[str, ResolvedCandidate] = {}
    for entry in by_code.values():
        display = normalize_vietnamese(entry.display)
        aliases = {normalize_vietnamese(alias) for alias in entry.aliases}
        if normalized == display:
            merged[entry.code] = ResolvedCandidate(
                entry.code,
                entry.display,
                entry.system,
                entry.mapping_revision,
                "exact",
                0.995,
                None,
            )
        elif normalized in aliases:
            merged[entry.code] = ResolvedCandidate(
                entry.code,
                entry.display,
                entry.system,
                entry.mapping_revision,
                "alias",
                0.96,
                None,
            )

    for dense in dense_candidates:
        dense_entry = by_code.get(dense.code)
        if dense_entry is None:
            continue
        if graph_allowed_codes is not None and dense.code not in graph_allowed_codes:
            continue
        confidence = _calibrate_dense(dense.similarity)
        existing = merged.get(dense.code)
        if existing is None or confidence > existing.confidence:
            merged[dense.code] = ResolvedCandidate(
                dense_entry.code,
                dense_entry.display,
                dense_entry.system,
                dense_entry.mapping_revision,
                "dense",
                confidence,
                None,
            )

    reranks = rerank_scores or {}
    bounded: list[ResolvedCandidate] = []
    for candidate in merged.values():
        score = reranks.get(candidate.code)
        safe_score = max(0.0, min(1.0, float(score))) if score is not None else None
        # Reranking may reorder but cannot introduce a code or increase the
        # calibrated confidence used for ambiguity.
        bounded.append(
            ResolvedCandidate(
                **{
                    **candidate.__dict__,
                    "rerank_score": safe_score,
                }
            )
        )
    bounded.sort(
        key=lambda item: (
            item.rerank_score if item.rerank_score is not None else item.confidence,
            item.confidence,
            item.code,
        ),
        reverse=True,
    )
    candidates = tuple(bounded[: max(1, min(top_k, 20))])
    if not candidates:
        status: Literal["resolved", "ambiguous", "unmapped"] = "unmapped"
    elif candidates[0].confidence < 0.75 or (
        len(candidates) > 1
        and candidates[0].confidence - candidates[1].confidence < 0.08
    ):
        status = "ambiguous"
    else:
        status = "resolved"
    return ResolutionResult(normalized, candidates, status)
