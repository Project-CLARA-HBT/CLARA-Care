"""Curated Vietnamese golden set for the CLARA Research quality harness (R17).

This module is the *measurable-quality seed* for the enhanced Research pipeline:
a curated, Vietnamese-first set of representative clinical / medication research
queries with reference relevant documents, reference (gold) answers, required
citations, and an expected refusal decision. The harness
(:mod:`clara_ml.research_quality.harness`) scores retrieval + synthesis quality
against these items, computing the five research-quality metrics and recording a
legacy baseline for recall@k (Requirements 17.1, 17.2).

Design constraints honoured here (mirroring :mod:`clara_ml.rag.eval.golden_set`):

* **Import-safe / pure data.** Importing this module performs no I/O, opens no
  database connection, and imports no ORM machinery. :data:`DEFAULT_RESEARCH_GOLDEN_SET`
  and :func:`load_research_golden_set` are pure in-memory data.
* **Vietnamese-first.** Each item's primary query (`query_vi`) and gold answer
  (`gold_answer_vi`) are authored in Vietnamese to match the product's default
  output language; an English gloss (`query_en`) is provided for traceability.
* **No PII.** Every query and gold answer is authored, generic clinical
  knowledge (no real patient names, contact details, or identifiers).
* **Refusal coverage.** At least one item is an out-of-scope query marked
  ``should_refuse=True`` so the harness can score ``refusal_compliance``
  (Requirement 10.5 / 17.2).

``relevant_doc_ids`` / ``must_cite`` use stable source-scoped reference strings
(e.g. ``"dailymed:warfarin-spl"``) consistent with the rag eval golden set, so
the two harnesses share corpus references.

Validates: Requirements 17.1, 17.2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "RESEARCH_CATEGORIES",
    "ResearchGoldenItem",
    "DEFAULT_RESEARCH_GOLDEN_SET",
    "load_research_golden_set",
]


# The research-eval categories this golden set spans. ``out_of_scope`` is the
# refusal-coverage category (Requirement 10.5); the rest mirror the clinical /
# medication evidence categories used across the rag eval golden set.
RESEARCH_CATEGORIES: frozenset[str] = frozenset(
    {
        "ddi",  # drug-drug interaction
        "dosage",  # dosing guidance / limits
        "contraindication",  # when a drug must not be used
        "indication",  # what a drug is used for
        "adverse_reaction",  # adverse effects / toxicity
        "safety",  # general safety / monitoring / overdose
        "out_of_scope",  # refusal coverage (non-medical / out-of-scope)
    }
)


@dataclass(frozen=True, slots=True)
class ResearchGoldenItem:
    """One curated Vietnamese research-evaluation item.

    Attributes
    ----------
    qid:
        Stable identifier for the item.
    query_vi:
        The Vietnamese research query the harness submits to the pipeline.
    category:
        One of :data:`RESEARCH_CATEGORIES`.
    query_en:
        Optional English gloss of the query (traceability only).
    expected_rxcui:
        Optional RxNorm ingredient ids relevant to the query.
    relevant_doc_ids:
        Gold-relevant document references scored by ``recall@k``.
    gold_answer_vi:
        Reference Vietnamese answer used for faithfulness / unsupported-claim
        scoring against retrieved context.
    must_cite:
        Citation targets that a faithful answer is required to cite
        (scored by ``citation_accuracy``).
    should_refuse:
        Whether the pipeline is expected to refuse this query (an out-of-scope
        item). Scored by ``refusal_compliance`` (Requirement 10.5).
    """

    qid: str
    query_vi: str
    category: str
    query_en: str = ""
    expected_rxcui: list[str] = field(default_factory=list)
    relevant_doc_ids: list[str] = field(default_factory=list)
    gold_answer_vi: str = ""
    must_cite: list[str] = field(default_factory=list)
    should_refuse: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a plain-dict view (lists copied) for serialization / logging."""

        return {
            "qid": self.qid,
            "query_vi": self.query_vi,
            "query_en": self.query_en,
            "category": self.category,
            "expected_rxcui": list(self.expected_rxcui),
            "relevant_doc_ids": list(self.relevant_doc_ids),
            "gold_answer_vi": self.gold_answer_vi,
            "must_cite": list(self.must_cite),
            "should_refuse": self.should_refuse,
        }


# ---------------------------------------------------------------------------
# Curated golden set (spans every category, includes refusal coverage)
# ---------------------------------------------------------------------------

DEFAULT_RESEARCH_GOLDEN_SET: list[ResearchGoldenItem] = [
    # --- Drug-drug interactions (ddi) -------------------------------------
    ResearchGoldenItem(
        qid="rq-ddi-aspirin-warfarin",
        category="ddi",
        query_vi="Phối hợp aspirin và warfarin ảnh hưởng thế nào đến nguy cơ chảy máu?",
        query_en="How does combining aspirin and warfarin affect bleeding risk?",
        expected_rxcui=["1191", "11289"],
        relevant_doc_ids=["dailymed:warfarin-spl", "dailymed:aspirin-spl"],
        gold_answer_vi=(
            "Phối hợp aspirin với warfarin làm tăng đáng kể nguy cơ chảy máu do tác động cộng "
            "hợp lên quá trình đông máu và kết tập tiểu cầu. Cần tránh phối hợp khi không cần "
            "thiết hoặc theo dõi INR chặt chẽ dưới sự giám sát của bác sĩ."
        ),
        must_cite=["dailymed:warfarin-spl", "openfda:label:warfarin"],
    ),
    ResearchGoldenItem(
        qid="rq-ddi-clopidogrel-omeprazole",
        category="ddi",
        query_vi="Omeprazole có làm giảm hiệu quả chống kết tập tiểu cầu của clopidogrel không?",
        query_en="Does omeprazole reduce the antiplatelet effect of clopidogrel?",
        expected_rxcui=["32968", "7646"],
        relevant_doc_ids=["dailymed:clopidogrel-spl"],
        gold_answer_vi=(
            "Omeprazole ức chế enzyme CYP2C19 cần để hoạt hóa clopidogrel, do đó có thể làm giảm "
            "tác dụng chống kết tập tiểu cầu. Nếu cần thuốc ức chế bơm proton, nên cân nhắc lựa "
            "chọn ít tương tác hơn như pantoprazole theo tư vấn của bác sĩ."
        ),
        must_cite=["dailymed:clopidogrel-spl"],
    ),
    # --- Dosage (dosage) ---------------------------------------------------
    ResearchGoldenItem(
        qid="rq-dosage-metformin-adult",
        category="dosage",
        query_vi="Liều khởi đầu và liều tối đa hằng ngày của metformin ở người lớn là bao nhiêu?",
        query_en="What is the starting and maximum daily dose of metformin in adults?",
        expected_rxcui=["6809"],
        relevant_doc_ids=["dailymed:metformin-spl"],
        gold_answer_vi=(
            "Liều khởi đầu thường gặp của metformin phóng thích tức thì ở người lớn là 500 mg "
            "uống một đến hai lần mỗi ngày cùng bữa ăn, tăng dần theo dung nạp. Liều tối đa "
            "thường không vượt quá 2000–2550 mg mỗi ngày và do bác sĩ chỉ định."
        ),
        must_cite=["dailymed:metformin-spl"],
    ),
    # --- Contraindication (contraindication) ------------------------------
    ResearchGoldenItem(
        qid="rq-contraindication-metformin-renal",
        category="contraindication",
        query_vi="Vì sao metformin chống chỉ định ở người suy thận nặng?",
        query_en="Why is metformin contraindicated in severe renal impairment?",
        expected_rxcui=["6809"],
        relevant_doc_ids=["dailymed:metformin-spl"],
        gold_answer_vi=(
            "Metformin chống chỉ định khi suy thận nặng vì giảm thải trừ làm tăng nguy cơ nhiễm "
            "toan lactic, một biến chứng hiếm nhưng nguy hiểm. Cần đánh giá chức năng thận trước "
            "và trong quá trình điều trị."
        ),
        must_cite=["dailymed:metformin-spl"],
    ),
    # --- Indication (indication) ------------------------------------------
    ResearchGoldenItem(
        qid="rq-indication-amoxicillin",
        category="indication",
        query_vi="Amoxicillin được chỉ định điều trị những nhiễm khuẩn nào?",
        query_en="What infections is amoxicillin indicated to treat?",
        expected_rxcui=["723"],
        relevant_doc_ids=["dailymed:amoxicillin-spl"],
        gold_answer_vi=(
            "Amoxicillin là kháng sinh nhóm penicillin dùng điều trị các nhiễm khuẩn nhạy cảm "
            "như viêm tai giữa, viêm họng do liên cầu, viêm xoang và viêm phổi mắc phải cộng "
            "đồng. Thuốc không có tác dụng với nhiễm virus."
        ),
        must_cite=["dailymed:amoxicillin-spl"],
    ),
    # --- Adverse reaction (adverse_reaction) ------------------------------
    ResearchGoldenItem(
        qid="rq-adverse-statin-myopathy",
        category="adverse_reaction",
        query_vi="Statin như simvastatin có thể gây tác dụng phụ trên cơ nào?",
        query_en="What muscle-related adverse effects can statins like simvastatin cause?",
        expected_rxcui=["36567"],
        relevant_doc_ids=["dailymed:simvastatin-spl"],
        gold_answer_vi=(
            "Statin có thể gây đau cơ, yếu cơ và hiếm gặp hơn là tiêu cơ vân, đặc biệt ở liều "
            "cao hoặc khi phối hợp với thuốc làm tăng nồng độ statin. Nếu đau cơ không rõ nguyên "
            "nhân kèm nước tiểu sẫm màu, cần ngừng thuốc và đi khám ngay."
        ),
        must_cite=["dailymed:simvastatin-spl"],
    ),
    # --- Safety (safety) ---------------------------------------------------
    ResearchGoldenItem(
        qid="rq-safety-paracetamol-overdose",
        category="safety",
        query_vi="Liều paracetamol tối đa mỗi ngày cho người lớn để tránh ngộ độc gan là bao nhiêu?",
        query_en="What is the maximum daily paracetamol dose for adults to avoid liver toxicity?",
        expected_rxcui=["161"],
        relevant_doc_ids=["dailymed:acetaminophen-spl"],
        gold_answer_vi=(
            "Người lớn thường không nên dùng quá 3–4 g paracetamol mỗi ngày vì quá liều có thể "
            "gây tổn thương gan nghiêm trọng. Cần thận trọng vì paracetamol có trong nhiều chế "
            "phẩm phối hợp; nếu nghi ngờ quá liều cần đến cơ sở y tế ngay."
        ),
        must_cite=["dailymed:acetaminophen-spl"],
    ),
    ResearchGoldenItem(
        qid="rq-safety-warfarin-inr-monitoring",
        category="safety",
        query_vi="Khi dùng warfarin cần theo dõi xét nghiệm gì để đảm bảo an toàn?",
        query_en="What monitoring is required for safe warfarin use?",
        expected_rxcui=["11289"],
        relevant_doc_ids=["dailymed:warfarin-spl"],
        gold_answer_vi=(
            "Người dùng warfarin cần theo dõi chỉ số INR định kỳ để đảm bảo mức chống đông nằm "
            "trong khoảng mục tiêu, vì INR quá cao làm tăng nguy cơ chảy máu còn quá thấp làm "
            "tăng nguy cơ huyết khối. Nhiều thực phẩm và thuốc có thể ảnh hưởng đến INR."
        ),
        must_cite=["dailymed:warfarin-spl"],
    ),
    # --- Out-of-scope (refusal coverage, R10.5) ---------------------------
    ResearchGoldenItem(
        qid="rq-out-of-scope-weather",
        category="out_of_scope",
        query_vi="Hôm nay thời tiết ở Hà Nội thế nào và tỷ giá đô la Mỹ là bao nhiêu?",
        query_en="What is today's weather in Hanoi and the USD exchange rate?",
        gold_answer_vi="",
        should_refuse=True,
    ),
]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_research_golden_set() -> list[ResearchGoldenItem]:
    """Return the curated Vietnamese research golden set.

    This is the replaceable seam for golden-set sourcing: it currently returns a
    fresh copy of :data:`DEFAULT_RESEARCH_GOLDEN_SET` (so callers cannot mutate
    the module constant), but can later be swapped for DB- or file-backed loading
    without changing the harness.
    """

    return list(DEFAULT_RESEARCH_GOLDEN_SET)
