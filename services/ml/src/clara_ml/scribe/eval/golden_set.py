"""Curated, non-PII golden set for the Scribe note-generation eval gate (task 9.1).

Mirrors the *evidence-of-improvement* seed of the research quality-gate
(:mod:`clara_ml.rag.eval.golden_set`) but for **note generation**: each item is a
realistic transcript→expected-structure pair used by the ``scribe_eval`` harness
(:mod:`clara_ml.scribe.eval.harness`) to measure structural completeness,
grounded-claim rate, no-fabrication, and a coding-precision proxy against declared
thresholds.

Design constraints honoured here (Requirement 20.5):

* **Import-safe / pure data.** Importing this module performs no I/O, opens no
  socket, and imports no ORM. :data:`DEFAULT_SCRIBE_GOLDEN_SET` and
  :func:`load_scribe_golden_set` are pure in-memory data.
* **NO PII.** Every transcript is authored, generic clinical dialogue — no real
  patient names, contact details, dates of birth, record numbers, or other
  identifiers. Speakers are the bounded diarization labels (``clinician`` /
  ``patient``) only.
* **Transcript→structure pairs.** Each item declares the template to generate, the
  ordered transcript segments (the ASR output a note would be generated from), and
  the expected advisory ICD-10 code(s) the documented conditions justify — so the
  harness can score coding precision without any patient data.

Validates: Requirement 20.5 (non-PII golden transcript→note pairs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "ScribeGoldenItem",
    "DEFAULT_SCRIBE_GOLDEN_SET",
    "load_scribe_golden_set",
]


@dataclass(frozen=True, slots=True)
class ScribeGoldenItem:
    """One golden transcript→expected-structure pair (non-PII).

    Attributes
    ----------
    case_id:
        Stable, non-PII identifier for the case.
    template_id:
        The note template to generate (must resolve in the templates registry).
    transcript_segments:
        Ordered ASR segment texts the note is generated from. Each segment is a
        full, self-contained clinical sentence (terminated) so it maps cleanly to
        one transcript span for grounding. Authored, generic, PII-free.
    expected_icd:
        The advisory ICD-10 code(s) the documented conditions defensibly justify;
        used to score the coding-precision proxy. Empty when no code is expected.
    category:
        Coarse case category for reporting (e.g. ``"chronic"`` / ``"acute"``).
    lang:
        Transcript language hint passed to the coding assistant (``"vi"`` / ``"en"``).
    """

    case_id: str
    template_id: str
    transcript_segments: list[str] = field(default_factory=list)
    expected_icd: list[str] = field(default_factory=list)
    category: str = ""
    lang: str = "vi"

    @property
    def transcript(self) -> str:
        """The full transcript text (segments joined in order)."""

        return " ".join(seg.strip() for seg in self.transcript_segments if seg.strip())

    def to_report_row(self) -> dict[str, Any]:
        """Non-PII descriptor for this case (no transcript text emitted)."""

        return {
            "case_id": self.case_id,
            "template_id": self.template_id,
            "category": self.category,
            "lang": self.lang,
            "segments": len(self.transcript_segments),
            "expected_icd": list(self.expected_icd),
        }


# ---------------------------------------------------------------------------
# Curated golden set (transcript→structure pairs, all non-PII)
# ---------------------------------------------------------------------------

DEFAULT_SCRIBE_GOLDEN_SET: list[ScribeGoldenItem] = [
    # --- Chronic, English, SOAP -------------------------------------------
    ScribeGoldenItem(
        case_id="soap-hypertension-en",
        template_id="soap",
        category="chronic",
        lang="en",
        transcript_segments=[
            "Patient reports occasional morning headaches over the past two weeks.",
            "Blood pressure measured in clinic is 150 over 95 today.",
            "Known history of hypertension managed with lifestyle measures.",
            "Plan is to continue home blood pressure monitoring and review in four weeks.",
        ],
        expected_icd=["I10"],
    ),
    # --- Chronic, Vietnamese, bệnh án -------------------------------------
    ScribeGoldenItem(
        case_id="benhan-dtd-vi",
        template_id="vn_benh_an",
        category="chronic",
        lang="vi",
        transcript_segments=[
            "Người bệnh than mệt mỏi và khát nước nhiều trong một tháng nay.",
            "Tiền sử đái tháo đường type 2 đang theo dõi tại phòng khám.",
            "Đường huyết đói hôm nay đo được 9 phẩy 2 milimol trên lít.",
            "Kế hoạch tiếp tục chế độ ăn và hẹn tái khám sau hai tuần.",
        ],
        expected_icd=["E11.9"],
    ),
    # --- Chronic, English, H&P --------------------------------------------
    ScribeGoldenItem(
        case_id="hp-asthma-en",
        template_id="h_and_p",
        category="chronic",
        lang="en",
        transcript_segments=[
            "Patient describes intermittent wheezing and shortness of breath at night.",
            "There is a documented history of asthma since childhood.",
            "Lungs reveal mild expiratory wheeze on examination today.",
            "Plan is to continue the inhaled reliever and review symptom control.",
        ],
        expected_icd=["J45.909"],
    ),
    # --- Acute, Vietnamese, progress note ---------------------------------
    ScribeGoldenItem(
        case_id="progress-viemphoi-vi",
        template_id="progress_note",
        category="acute",
        lang="vi",
        transcript_segments=[
            "Người bệnh sốt và ho có đàm trong ba ngày gần đây.",
            "Chẩn đoán hiện tại là viêm phổi cộng đồng mức độ nhẹ.",
            "Phổi nghe có ran ẩm đáy phổi phải khi thăm khám.",
            "Kế hoạch theo dõi sát và đánh giá lại sau bốn mươi tám giờ.",
        ],
        expected_icd=["J18.9"],
    ),
    # --- Acute, English, SOAP ---------------------------------------------
    ScribeGoldenItem(
        case_id="soap-migraine-en",
        template_id="soap",
        category="acute",
        lang="en",
        transcript_segments=[
            "Patient reports a throbbing one sided headache with light sensitivity.",
            "The pattern is consistent with migraine without aura.",
            "Neurological examination is unremarkable today.",
            "Plan is to advise rest in a dark room and review if symptoms persist.",
        ],
        expected_icd=["G43.909"],
    ),
    # --- Acute, English, referral letter ----------------------------------
    ScribeGoldenItem(
        case_id="referral-anxiety-en",
        template_id="referral_letter",
        category="acute",
        lang="en",
        transcript_segments=[
            "Patient describes persistent worry and difficulty sleeping for months.",
            "The presentation is consistent with a generalized anxiety disorder.",
            "No acute risk concerns were identified on review today.",
            "Requesting outpatient psychology assessment and ongoing support.",
        ],
        expected_icd=["F41.9"],
    ),
]


def load_scribe_golden_set() -> list[ScribeGoldenItem]:
    """Return the curated golden transcript→structure set (a fresh list copy).

    This is the replaceable seam for golden-set sourcing: it currently returns
    :data:`DEFAULT_SCRIBE_GOLDEN_SET`, but can later be swapped for file-backed
    loading without changing the harness.
    """

    return list(DEFAULT_SCRIBE_GOLDEN_SET)
