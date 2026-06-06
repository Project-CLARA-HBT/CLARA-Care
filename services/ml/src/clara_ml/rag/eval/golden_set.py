"""Golden Vietnamese Q&A evaluation set for the RAG knowledge pipeline (task 9.1).

This module is the *evidence-of-improvement* seed: a curated set of realistic
Vietnamese medical questions with gold entities (RXCUI), gold-relevant document
references, authored Vietnamese gold answers, and citation targets. The eval
harness (task 9.4) scores retrieval + answer quality against these items and
records ``eval_run_result`` rows.

Design constraints honoured here:

* **Import-safe / pure data.** Importing this module performs no I/O, opens no
  database connection, and imports no ORM machinery. :data:`DEFAULT_GOLDEN_SET`
  and :func:`load_golden_set` are pure in-memory data; the only database
  coupling lives inside :func:`seed_eval_set`, which imports the ORM lazily.
* **Schema-mirroring.** :class:`GoldenItem` mirrors the ``eval_set`` columns
  defined in :mod:`clara_ml.rag.store.schema` (``qid``, ``question_vi``,
  ``question_en``, ``expected_rxcui``, ``relevant_doc_ids``, ``gold_answer_vi``,
  ``must_cite``, ``category``) so seeding is a direct column map.
* **Idempotent UPSERT on ``qid``.** :func:`seed_eval_set` inserts new golden
  items and updates existing ones keyed on the stable ``qid``, so re-seeding is
  a no-op on unchanged content and never duplicates a row.
* **No PII.** Every question and gold answer is authored, generic clinical
  knowledge (no real patient names, contact details, or identifiers).

Validates: Requirement 11.1 (golden VN Q&A ``eval_set`` with ``question_vi``,
``expected_rxcui``, ``relevant_doc_ids``, ``must_cite``, ``category``).

RXCUI values use RxNorm ingredient-level identifiers as realistic placeholders.
``relevant_doc_ids`` / ``must_cite`` use stable source-scoped reference strings
(e.g. ``"dailymed:warfarin-spl"``) that resolve to corpus documents / citation
targets once the offline ingestion plane has populated the corpus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "CATEGORIES",
    "GoldenItem",
    "DEFAULT_GOLDEN_SET",
    "load_golden_set",
    "seed_eval_set",
]


# The eval categories this golden set spans. Mirrors the ``category`` tags used
# on each :class:`GoldenItem` and the design's category vocabulary.
CATEGORIES: frozenset[str] = frozenset(
    {
        "ddi",  # drug-drug interaction
        "dosage",  # dosing guidance / limits
        "contraindication",  # when a drug must not be used
        "indication",  # what a drug is used for
        "adverse_reaction",  # adverse effects / toxicity
        "safety",  # general safety / monitoring / overdose
    }
)


@dataclass(frozen=True, slots=True)
class GoldenItem:
    """One golden Vietnamese Q&A item mirroring an ``eval_set`` row.

    Attributes map 1:1 to the ``eval_set`` columns. List-valued fields default
    to empty lists so partially specified items stay valid; the seeder copies
    them defensively before persisting.
    """

    qid: str
    question_vi: str
    category: str
    question_en: str = ""
    expected_rxcui: list[str] = field(default_factory=list)
    relevant_doc_ids: list[str] = field(default_factory=list)
    gold_answer_vi: str = ""
    must_cite: list[str] = field(default_factory=list)

    def to_eval_row(self) -> dict[str, Any]:
        """Return the ``eval_set`` column map for this item (lists copied)."""

        return {
            "qid": self.qid,
            "question_vi": self.question_vi,
            "question_en": self.question_en,
            "expected_rxcui": list(self.expected_rxcui),
            "relevant_doc_ids": list(self.relevant_doc_ids),
            "gold_answer_vi": self.gold_answer_vi,
            "must_cite": list(self.must_cite),
            "category": self.category,
        }


# ---------------------------------------------------------------------------
# Curated golden set (>= 10 items spanning all six categories)
# ---------------------------------------------------------------------------

DEFAULT_GOLDEN_SET: list[GoldenItem] = [
    # --- Drug-drug interactions (ddi) -------------------------------------
    GoldenItem(
        qid="ddi-aspirin-warfarin",
        category="ddi",
        question_vi="Dùng aspirin chung với warfarin có làm tăng nguy cơ chảy máu không?",
        question_en="Does taking aspirin together with warfarin increase bleeding risk?",
        expected_rxcui=["1191", "11289"],
        relevant_doc_ids=["dailymed:warfarin-spl", "dailymed:aspirin-spl"],
        gold_answer_vi=(
            "Có. Aspirin kết hợp với warfarin làm tăng đáng kể nguy cơ chảy máu do tác động "
            "cộng hợp lên quá trình đông máu. Cần tránh phối hợp hoặc theo dõi INR chặt chẽ và "
            "chỉ dùng khi có chỉ định và giám sát của bác sĩ."
        ),
        must_cite=["dailymed:warfarin-spl", "openfda:label:warfarin"],
    ),
    GoldenItem(
        qid="ddi-clopidogrel-omeprazole",
        category="ddi",
        question_vi="Omeprazole có làm giảm tác dụng của clopidogrel không?",
        question_en="Does omeprazole reduce the effectiveness of clopidogrel?",
        expected_rxcui=["32968", "7646"],
        relevant_doc_ids=["dailymed:clopidogrel-spl"],
        gold_answer_vi=(
            "Có thể. Omeprazole ức chế enzyme CYP2C19 vốn cần để hoạt hóa clopidogrel, do đó có "
            "thể làm giảm tác dụng chống kết tập tiểu cầu. Nếu cần thuốc ức chế bơm proton, nên "
            "cân nhắc lựa chọn ít tương tác hơn như pantoprazole theo tư vấn của bác sĩ."
        ),
        must_cite=["dailymed:clopidogrel-spl", "openfda:label:clopidogrel"],
    ),
    GoldenItem(
        qid="ddi-acei-potassium-hyperkalemia",
        category="ddi",
        question_vi=(
            "Dùng thuốc ức chế men chuyển (ACE) cùng với bổ sung kali có gây tăng kali máu không?"
        ),
        question_en=(
            "Can an ACE inhibitor combined with potassium supplements cause hyperkalemia?"
        ),
        expected_rxcui=["29046", "8591"],
        relevant_doc_ids=["dailymed:lisinopril-spl"],
        gold_answer_vi=(
            "Có. Thuốc ức chế men chuyển làm giảm bài tiết kali, nên khi dùng chung với viên bổ "
            "sung kali hoặc thuốc lợi tiểu giữ kali có thể gây tăng kali máu nguy hiểm. Cần theo "
            "dõi nồng độ kali huyết thanh và chức năng thận định kỳ."
        ),
        must_cite=["dailymed:lisinopril-spl"],
    ),
    GoldenItem(
        qid="ddi-sildenafil-nitrate",
        category="ddi",
        question_vi="Có được dùng sildenafil khi đang dùng nitroglycerin không?",
        question_en="Can sildenafil be taken while using nitroglycerin?",
        expected_rxcui=["136411", "4917"],
        relevant_doc_ids=["dailymed:sildenafil-spl"],
        gold_answer_vi=(
            "Không. Phối hợp sildenafil với nitroglycerin hoặc các nitrat khác có thể gây tụt "
            "huyết áp nghiêm trọng, đe dọa tính mạng. Đây là chống chỉ định tuyệt đối; cần ngừng "
            "và hỏi ý kiến bác sĩ trước khi dùng."
        ),
        must_cite=["dailymed:sildenafil-spl", "openfda:label:sildenafil"],
    ),
    # --- Dosage (dosage) ---------------------------------------------------
    GoldenItem(
        qid="dosage-metformin-adult",
        category="dosage",
        question_vi="Liều khởi đầu thông thường của metformin ở người lớn là bao nhiêu?",
        question_en="What is the usual starting dose of metformin in adults?",
        expected_rxcui=["6809"],
        relevant_doc_ids=["dailymed:metformin-spl"],
        gold_answer_vi=(
            "Liều khởi đầu thường gặp của metformin phóng thích tức thì ở người lớn là 500 mg "
            "uống một đến hai lần mỗi ngày cùng bữa ăn, tăng dần theo dung nạp. Liều tối đa "
            "thường không vượt quá 2000–2550 mg mỗi ngày; liều cụ thể do bác sĩ chỉ định."
        ),
        must_cite=["dailymed:metformin-spl"],
    ),
    GoldenItem(
        qid="dosage-amoxicillin-pediatric",
        category="dosage",
        question_vi="Liều amoxicillin cho trẻ em được tính như thế nào?",
        question_en="How is the amoxicillin dose calculated for children?",
        expected_rxcui=["723"],
        relevant_doc_ids=["dailymed:amoxicillin-spl"],
        gold_answer_vi=(
            "Liều amoxicillin ở trẻ em thường được tính theo cân nặng, phổ biến khoảng "
            "20–45 mg/kg/ngày chia làm 2–3 lần tùy mức độ nhiễm khuẩn. Cần tuân theo chỉ định và "
            "cân nặng thực tế của trẻ; không tự ý dùng lại đơn cũ."
        ),
        must_cite=["dailymed:amoxicillin-spl"],
    ),
    # --- Contraindication (contraindication) ------------------------------
    GoldenItem(
        qid="contraindication-metformin-renal",
        category="contraindication",
        question_vi="Metformin có chống chỉ định ở người suy thận nặng không?",
        question_en="Is metformin contraindicated in severe renal impairment?",
        expected_rxcui=["6809"],
        relevant_doc_ids=["dailymed:metformin-spl"],
        gold_answer_vi=(
            "Có. Metformin chống chỉ định khi suy thận nặng (ví dụ eGFR dưới 30 mL/phút/1,73m²) "
            "vì tăng nguy cơ nhiễm toan lactic. Cần đánh giá chức năng thận trước và trong khi "
            "điều trị."
        ),
        must_cite=["dailymed:metformin-spl", "openfda:label:metformin"],
    ),
    GoldenItem(
        qid="contraindication-nsaid-peptic-ulcer",
        category="contraindication",
        question_vi="Người có loét dạ dày tiến triển có nên dùng ibuprofen không?",
        question_en="Should a person with active peptic ulcer use ibuprofen?",
        expected_rxcui=["5640"],
        relevant_doc_ids=["dailymed:ibuprofen-spl"],
        gold_answer_vi=(
            "Không nên. Ibuprofen và các thuốc kháng viêm không steroid (NSAID) chống chỉ định "
            "tương đối ở người loét dạ dày tiến triển vì làm tăng nguy cơ xuất huyết và thủng "
            "tiêu hóa. Nên dùng thuốc giảm đau thay thế và hỏi ý kiến bác sĩ."
        ),
        must_cite=["dailymed:ibuprofen-spl"],
    ),
    # --- Indication (indication) ------------------------------------------
    GoldenItem(
        qid="indication-amoxicillin",
        category="indication",
        question_vi="Amoxicillin được dùng để điều trị những bệnh gì?",
        question_en="What conditions is amoxicillin used to treat?",
        expected_rxcui=["723"],
        relevant_doc_ids=["dailymed:amoxicillin-spl"],
        gold_answer_vi=(
            "Amoxicillin là kháng sinh nhóm penicillin dùng điều trị các nhiễm khuẩn nhạy cảm "
            "như viêm tai giữa, viêm họng do liên cầu, viêm xoang, viêm phổi mắc phải cộng đồng "
            "và một số nhiễm khuẩn đường tiết niệu. Chỉ dùng khi có chỉ định, không dùng cho "
            "nhiễm virus."
        ),
        must_cite=["dailymed:amoxicillin-spl"],
    ),
    GoldenItem(
        qid="indication-aspirin-secondary-prevention",
        category="indication",
        question_vi="Aspirin liều thấp được dùng để làm gì trong dự phòng tim mạch?",
        question_en="What is low-dose aspirin used for in cardiovascular prevention?",
        expected_rxcui=["1191"],
        relevant_doc_ids=["dailymed:aspirin-spl"],
        gold_answer_vi=(
            "Aspirin liều thấp được dùng để dự phòng thứ phát các biến cố tim mạch ở người đã "
            "từng nhồi máu cơ tim hoặc đột quỵ do thiếu máu cục bộ, nhờ tác dụng chống kết tập "
            "tiểu cầu. Việc dùng để dự phòng tiên phát cần cân nhắc nguy cơ chảy máu và do bác "
            "sĩ quyết định."
        ),
        must_cite=["dailymed:aspirin-spl"],
    ),
    # --- Adverse reaction (adverse_reaction) ------------------------------
    GoldenItem(
        qid="adverse-statin-myopathy",
        category="adverse_reaction",
        question_vi="Statin như simvastatin có thể gây đau cơ hay tiêu cơ vân không?",
        question_en="Can statins like simvastatin cause myopathy or rhabdomyolysis?",
        expected_rxcui=["36567"],
        relevant_doc_ids=["dailymed:simvastatin-spl"],
        gold_answer_vi=(
            "Có. Statin có thể gây đau cơ, yếu cơ và hiếm gặp hơn là tiêu cơ vân, đặc biệt ở "
            "liều cao hoặc khi phối hợp với một số thuốc làm tăng nồng độ statin. Nếu xuất hiện "
            "đau cơ không rõ nguyên nhân kèm nước tiểu sẫm màu, cần ngừng thuốc và đi khám ngay."
        ),
        must_cite=["dailymed:simvastatin-spl", "openfda:label:simvastatin"],
    ),
    GoldenItem(
        qid="adverse-acei-cough",
        category="adverse_reaction",
        question_vi="Vì sao thuốc ức chế men chuyển như lisinopril gây ho khan?",
        question_en="Why do ACE inhibitors like lisinopril cause a dry cough?",
        expected_rxcui=["29046"],
        relevant_doc_ids=["dailymed:lisinopril-spl"],
        gold_answer_vi=(
            "Thuốc ức chế men chuyển có thể gây ho khan dai dẳng do tích tụ bradykinin ở đường "
            "hô hấp. Đây là tác dụng phụ thường gặp và không nguy hiểm, nhưng nếu khó chịu, bác "
            "sĩ có thể chuyển sang nhóm chẹn thụ thể angiotensin (ARB)."
        ),
        must_cite=["dailymed:lisinopril-spl"],
    ),
    # --- Safety (safety) ---------------------------------------------------
    GoldenItem(
        qid="safety-paracetamol-overdose",
        category="safety",
        question_vi="Liều paracetamol tối đa mỗi ngày cho người lớn là bao nhiêu để tránh ngộ độc gan?",
        question_en="What is the maximum daily paracetamol dose for adults to avoid liver toxicity?",
        expected_rxcui=["161"],
        relevant_doc_ids=["dailymed:acetaminophen-spl"],
        gold_answer_vi=(
            "Người lớn thường không nên dùng quá 3–4 g paracetamol mỗi ngày, vì quá liều có thể "
            "gây tổn thương gan nghiêm trọng. Cần thận trọng vì paracetamol có trong nhiều chế "
            "phẩm phối hợp; nếu nghi ngờ quá liều, đến cơ sở y tế ngay vì có thuốc giải độc "
            "N-acetylcystein."
        ),
        must_cite=["dailymed:acetaminophen-spl", "openfda:label:acetaminophen"],
    ),
    GoldenItem(
        qid="safety-warfarin-inr-monitoring",
        category="safety",
        question_vi="Khi dùng warfarin cần theo dõi xét nghiệm gì và vì sao?",
        question_en="What monitoring is required when taking warfarin and why?",
        expected_rxcui=["11289"],
        relevant_doc_ids=["dailymed:warfarin-spl"],
        gold_answer_vi=(
            "Người dùng warfarin cần theo dõi chỉ số INR định kỳ để đảm bảo mức chống đông nằm "
            "trong khoảng mục tiêu, vì INR quá cao làm tăng nguy cơ chảy máu còn quá thấp làm "
            "tăng nguy cơ huyết khối. Nhiều thực phẩm và thuốc có thể ảnh hưởng đến INR nên cần "
            "tư vấn bác sĩ."
        ),
        must_cite=["dailymed:warfarin-spl"],
    ),
]


# ---------------------------------------------------------------------------
# Loading + seeding
# ---------------------------------------------------------------------------


def load_golden_set() -> list[GoldenItem]:
    """Return the curated golden Vietnamese Q&A set.

    This is the replaceable seam for golden-set sourcing: it currently returns
    :data:`DEFAULT_GOLDEN_SET` (a fresh list copy so callers cannot mutate the
    module constant), but can later be swapped for DB-backed or file-backed
    loading without changing the harness.
    """

    return list(DEFAULT_GOLDEN_SET)


def seed_eval_set(
    store_or_session: Any,
    *,
    items: list[GoldenItem] | None = None,
) -> int:
    """Idempotently UPSERT golden items into the ``eval_set`` table (UPSERT on ``qid``).

    Validates: Requirement 11.1.

    Parameters
    ----------
    store_or_session:
        One of:

        * a :class:`~clara_ml.rag.store.document_store.DocumentStore` (anything
          exposing a ``transaction()`` context manager) — the seed runs inside
          its atomic transaction;
        * a live SQLAlchemy :class:`~sqlalchemy.orm.Session` — rows are staged
          and committed on the session;
        * a zero-argument session factory / ``sessionmaker`` — a session is
          created, used, committed, and closed.
    items:
        Optional explicit golden items to seed. Defaults to
        :func:`load_golden_set`.

    Returns
    -------
    int
        The number of golden items seeded (inserted or updated).

    Notes
    -----
    The ORM is imported lazily here so the module stays import-safe and free of
    database coupling for the pure-data path. Idempotency is keyed on the stable
    ``qid``: an existing row is updated in place, a missing row is inserted, and
    re-seeding unchanged content produces no duplicates.
    """

    rows = list(items) if items is not None else load_golden_set()

    # Lazy ORM import keeps the pure-data path (load_golden_set / DEFAULT_GOLDEN_SET)
    # free of SQLAlchemy coupling and side effects at import time.
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from clara_ml.rag.store.schema import EvalSet

    def _upsert(session: Session) -> int:
        count = 0
        for item in rows:
            values = item.to_eval_row()
            existing = session.execute(
                select(EvalSet).where(EvalSet.qid == item.qid)
            ).scalar_one_or_none()
            if existing is not None:
                # UPSERT on qid: update every mutable column in place.
                for key, value in values.items():
                    if key == "qid":
                        continue
                    setattr(existing, key, value)
            else:
                session.add(EvalSet(**values))
            count += 1
        session.flush()
        return count

    # Dispatch on the kind of handle provided (mirrors ingestion.scheduler):
    # 1) DocumentStore-like — reuse its transactional boundary (commit/rollback).
    transaction = getattr(store_or_session, "transaction", None)
    if callable(transaction) and not isinstance(store_or_session, Session):
        with transaction() as session:
            return _upsert(session)

    # 2) Live Session — operate on it and commit.
    if isinstance(store_or_session, Session):
        seeded = _upsert(store_or_session)
        store_or_session.commit()
        return seeded

    # 3) Session factory — open / commit / close our own short transaction.
    if callable(store_or_session):
        session = store_or_session()
        try:
            seeded = _upsert(session)
            session.commit()
            return seeded
        finally:
            session.close()

    raise TypeError(
        "seed_eval_set expects a DocumentStore, a SQLAlchemy Session, or a "
        f"zero-argument session factory; got {type(store_or_session)!r}"
    )
