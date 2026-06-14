"""Note-generation evaluation gate harness for Clara Scribe (task 9.1, Req 20).

A ``scribe_eval`` golden-set harness, gated by ``RAG_SCRIBE_EVAL_GATE_ENABLED``,
that **mirrors the CLARA Research quality-gate pattern**
(:mod:`clara_ml.rag.eval.harness` — its ``EvalSummary`` + pure ``gate()``). It runs
note generation (:class:`~clara_ml.scribe.generator.NoteGenerator`) over a curated,
**non-PII** golden set of transcript→note pairs
(:mod:`clara_ml.scribe.eval.golden_set`) and computes at least four metrics, each
compared against a declared threshold (Req 20.2):

* **structural_completeness** — every generated note has EXACTLY its template's
  declared section keys (reuses the Requirement 6 structure guarantee).
* **grounded_claim_rate** — fraction of clinically significant note statements
  entailed by a transcript span, via the existing
  :class:`~clara_ml.scribe.grounding.GroundingVerifier` (reuses the FIDES/NLI
  claim-verification path).
* **no_fabrication** — fraction of cases where the note asserts no ungrounded
  critical-safety statement as fact (reuses the grounding verdicts; Req 6.5/12.5).
* **coding_precision** — proxy precision of the advisory ICD-10 suggestions
  (:class:`~clara_ml.scribe.coding.CodingAssistant`) against the golden expected
  codes.

The gate passes *iff* every metric meets its threshold; when any threshold is
unmet it reports failure and **names the breaching metric(s)** (Req 20.3/20.4),
mirroring the research quality-gate so a regression blocks release.

Design constraints (Requirement 20):

* **Flag-gated (Req 20.1).** When ``RAG_SCRIBE_EVAL_GATE_ENABLED`` is off the
  harness does not run: :meth:`ScribeEvalHarness.run` returns an inert,
  empty-metrics :class:`EvalGateResult` (``passed=True``) and performs no note
  generation, so it never affects runtime behavior.
* **Offline/CI only (Req 20.1/20.6).** This module is never wired into the runtime
  note-generation path; it is import-safe (no socket on import) and
  dependency-injected so it runs end-to-end with no database.
* **PII-free (Req 20.5).** Golden data is authored + non-PII and
  :meth:`EvalGateResult.as_dict` emits only metric names/values and coarse case
  descriptors — never transcript text or patient identifiers.

The pure :func:`build_gate_result` (and the value-object :class:`EvalMetric`) is the
deterministic threshold-enforcement core that task 9.2 (Property 15) exercises.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from clara_ml.config import settings
from clara_ml.scribe.coding import CodingAssistant
from clara_ml.scribe.eval.golden_set import ScribeGoldenItem, load_scribe_golden_set
from clara_ml.scribe.generator import Note, NoteGenerator
from clara_ml.scribe.grounding import GroundingReport, GroundingVerifier
from clara_ml.scribe.provenance import SpanRegistry
from clara_ml.scribe.templates import get_template

__all__ = [
    "EvalMetric",
    "EvalGateResult",
    "DEFAULT_THRESHOLDS",
    "build_gate_result",
    "ScribeEvalHarness",
]


# Declared default thresholds for each computed metric (Req 20.2/20.3). Each is a
# minimum the metric value must MEET (``value >= threshold``) for the gate to pass.
DEFAULT_THRESHOLDS: dict[str, float] = {
    "structural_completeness": 1.0,
    "grounded_claim_rate": 0.60,
    "no_fabrication": 1.0,
    "coding_precision": 0.80,
}


# ---------------------------------------------------------------------------
# Value objects (mirror design.md component 14)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EvalMetric:
    """One computed metric compared against its declared threshold.

    ``passed`` is ``value >= threshold`` (a metric is a *minimum* floor). Use
    :meth:`create` so the pass/fail invariant is always derived consistently.
    """

    name: str
    value: float
    threshold: float
    passed: bool

    @classmethod
    def create(cls, name: str, value: float, threshold: float) -> EvalMetric:
        """Build a metric, deriving ``passed = value >= threshold``."""

        v = float(value)
        t = float(threshold)
        return cls(name=str(name), value=v, threshold=t, passed=v >= t)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": round(self.value, 4),
            "threshold": round(self.threshold, 4),
            "passed": self.passed,
        }


@dataclass(frozen=True, slots=True)
class EvalGateResult:
    """Aggregate gate verdict over a set of metrics.

    ``passed`` is ``all(m.passed for m in metrics)`` and ``failing`` names every
    metric that breached its threshold (Req 20.3/20.4). Built via
    :func:`build_gate_result` so the verdict is always consistent with ``metrics``.
    """

    metrics: list[EvalMetric] = field(default_factory=list)
    passed: bool = True
    failing: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Non-PII report: metric names/values + verdict only (no transcript text)."""

        return {
            "version": "scribe-eval-gate-v1",
            "passed": self.passed,
            "failing": list(self.failing),
            "metrics": [m.as_dict() for m in self.metrics],
        }


def build_gate_result(metrics: Iterable[EvalMetric]) -> EvalGateResult:
    """Aggregate ``metrics`` into an :class:`EvalGateResult` (pure, deterministic).

    Validates: Requirements 20.3, 20.4.

    The gate passes *iff* EVERY metric meets its threshold; otherwise it fails and
    ``failing`` lists the names of the breaching metric(s), in order. This is the
    deterministic enforcement core property test P15 (task 9.2) exercises — it
    reads only the ``passed`` flags on the metrics and performs no I/O.
    """

    ordered = list(metrics)
    failing = [m.name for m in ordered if not m.passed]
    return EvalGateResult(
        metrics=ordered,
        passed=not failing,
        failing=failing,
    )


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

GoldenLoader = Callable[[], Iterable[ScribeGoldenItem]]


class ScribeEvalHarness:
    """Run note generation over the golden set and enforce the declared thresholds.

    Parameters
    ----------
    generator:
        Injectable :class:`~clara_ml.scribe.generator.NoteGenerator`. Defaults to a
        deterministic, no-fabrication generator (no LLM) so the harness is offline.
    coding:
        Injectable :class:`~clara_ml.scribe.coding.CodingAssistant` for the
        coding-precision proxy. Defaults to an ICD-only assistant (E/M+CPT off) so
        the proxy scores the Requirement 7 ICD suggestions.
    grounding:
        Injectable :class:`~clara_ml.scribe.grounding.GroundingVerifier`. Defaults
        to one FORCED ON (``enabled=True``) regardless of the grounding runtime
        flag, because the eval gate computes the grounded-claim rate offline; this
        never affects the clinician runtime path (Req 20.6).
    golden_loader:
        Zero-arg callable returning the golden items. Defaults to
        :func:`~clara_ml.scribe.eval.golden_set.load_scribe_golden_set`.
    thresholds:
        Declared per-metric thresholds. Defaults to :data:`DEFAULT_THRESHOLDS`.
    enabled:
        Override for ``RAG_SCRIBE_EVAL_GATE_ENABLED`` (Req 20.1). When ``None`` the
        runtime flag is read; when ``False`` the harness is inert.
    """

    def __init__(
        self,
        *,
        generator: NoteGenerator | None = None,
        coding: CodingAssistant | None = None,
        grounding: GroundingVerifier | None = None,
        golden_loader: GoldenLoader = load_scribe_golden_set,
        thresholds: dict[str, float] | None = None,
        enabled: bool | None = None,
    ) -> None:
        self._generator = generator or NoteGenerator()
        self._coding = coding or CodingAssistant(em_cpt_enabled=False)
        # The eval gate measures grounding offline, so force the verifier on; the
        # runtime grounding flag is unrelated to whether the gate may compute it.
        self._grounding = grounding or GroundingVerifier(enabled=True)
        self._golden_loader = golden_loader
        self._thresholds = dict(thresholds) if thresholds is not None else dict(DEFAULT_THRESHOLDS)
        self._enabled = (
            bool(settings.rag_scribe_eval_gate_enabled) if enabled is None else bool(enabled)
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    # -- public API ----------------------------------------------------------

    def run(self) -> EvalGateResult:
        """Run the gate and return its :class:`EvalGateResult`.

        When ``RAG_SCRIBE_EVAL_GATE_ENABLED`` is off the gate does NOT run: it
        returns an inert, empty-metrics result (``passed=True``) and generates no
        notes, so it never affects runtime behavior (Req 20.1).

        Otherwise it generates a note for each golden item, computes the four
        metrics, and aggregates them into a pass/fail verdict that names any
        breaching metric (Req 20.2/20.3/20.4).
        """

        if not self._enabled:
            return EvalGateResult(metrics=[], passed=True, failing=[])

        items = list(self._golden_loader())
        return build_gate_result(self.compute_metrics(items))

    def compute_metrics(self, items: list[ScribeGoldenItem]) -> list[EvalMetric]:
        """Compute the four declared metrics over ``items`` (offline, no I/O)."""

        struct_hits = 0
        struct_total = 0

        grounded_significant = 0
        total_significant = 0

        no_fab_cases = 0
        fab_total = 0

        coding_correct = 0
        coding_suggested = 0

        for item in items:
            note = self._generator.generate(item.transcript, item.template_id)

            # 1. Structural completeness — exactly the template's section keys.
            struct_total += 1
            if self._is_structurally_complete(note, item.template_id):
                struct_hits += 1

            # 2/3. Grounding-derived metrics (grounded-claim rate + no-fabrication).
            report = self._grounding.verify(note, self._registry_for(item))
            grounded_significant += report.grounded_significant
            total_significant += report.total_significant
            fab_total += 1
            if not self._has_fabrication(report):
                no_fab_cases += 1

            # 4. Coding-precision proxy — advisory ICD vs golden expected codes.
            correct, suggested = self._score_coding(item, note)
            coding_correct += correct
            coding_suggested += suggested

        structural_completeness = _ratio(struct_hits, struct_total, default=1.0)
        grounded_claim_rate = _ratio(grounded_significant, total_significant, default=1.0)
        no_fabrication = _ratio(no_fab_cases, fab_total, default=1.0)
        coding_precision = _ratio(coding_correct, coding_suggested, default=1.0)

        return [
            EvalMetric.create(
                "structural_completeness",
                structural_completeness,
                self._thresholds.get("structural_completeness", 0.0),
            ),
            EvalMetric.create(
                "grounded_claim_rate",
                grounded_claim_rate,
                self._thresholds.get("grounded_claim_rate", 0.0),
            ),
            EvalMetric.create(
                "no_fabrication",
                no_fabrication,
                self._thresholds.get("no_fabrication", 0.0),
            ),
            EvalMetric.create(
                "coding_precision",
                coding_precision,
                self._thresholds.get("coding_precision", 0.0),
            ),
        ]

    # -- internal helpers ----------------------------------------------------

    @staticmethod
    def _registry_for(item: ScribeGoldenItem) -> SpanRegistry:
        """Build the per-case span registry from the golden transcript segments."""

        return SpanRegistry(list(item.transcript_segments))

    @staticmethod
    def _is_structurally_complete(note: Note, template_id: str) -> bool:
        """True when ``note`` has EXACTLY its template's declared section keys."""

        template = get_template(template_id, include_specialty=True)
        if template is None:
            return False
        return list(note.sections.keys()) == list(template.section_keys)

    @staticmethod
    def _has_fabrication(report: GroundingReport) -> bool:
        """True if the note contains an ungrounded critical-safety statement.

        A no-fabrication check on the *generated note text* (Req 6.5 / Req 20.2):
        a faithful generator only writes critical-safety content (medication, dose,
        allergy, vital, diagnosis) that a transcript span supports, so every
        significant critical statement is grounded. An ungrounded critical
        statement means the generator fabricated content the transcript never
        contained — exactly the regression this gate must catch — regardless of
        whether the runtime grounding pass would later suppress it from assertion.
        """

        return any(
            stmt.significant and stmt.critical_safety and not stmt.grounded
            for stmt in report.statements
        )

    def _score_coding(self, item: ScribeGoldenItem, note: Note) -> tuple[int, int]:
        """Return (correct, suggested) ICD codes for the coding-precision proxy.

        Precision is scored over the advisory ICD-10 suggestions: a suggested code
        is *correct* when it is in the golden ``expected_icd`` set. Cases with no
        suggestions contribute nothing to the denominator (handled by the caller's
        ratio default), so they neither help nor hurt the proxy.
        """

        note_text = "\n".join(str(v) for v in note.sections.values())
        result = self._coding.suggest(note_text, lang=item.lang)
        suggested_codes = [c.code for c in result.icd]
        expected = set(item.expected_icd)
        correct = sum(1 for code in suggested_codes if code in expected)
        return correct, len(suggested_codes)


def _ratio(numerator: int, denominator: int, *, default: float) -> float:
    """Return ``numerator / denominator`` in ``[0, 1]``, or ``default`` when empty."""

    if denominator <= 0:
        return float(default)
    return max(0.0, min(1.0, numerator / denominator))
