# 03-TECH-DESIGN: GLHS SOTA UPGRADE

**Tài liệu:** Thiết Kế Kỹ Thuật Chi Tiết & Đặc Tả Lược Đồ Dữ Liệu GLHS v2 (SOTA Edition)  
**Dự án:** CLARA-Care (Branch: `codex/commitloop-phase-a`)  
**Ngày lập:** Tháng 8/2026  

---

## 1. LƯỢC ĐỒ CƠ SỞ DỮ LIỆU & MÔ HÌNH ORM (POSTGRESQL 16 & SQLALCHEMY 2.0)

Để hiện thực hóa cơ chế **Entity-Partitioned Versioning** và **Immutable Cryptographic Lineage**, cấu trúc bảng trong `services/api/src/clara_api/db/models.py` được mở rộng và chuẩn hóa như sau:

```python
# services/api/src/clara_api/db/models.py (GLHS SOTA Subsystem)

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from clara_api.db.base import Base


class GlhsEntityVersionPartition(Base):
    """Lưu trữ vector phiên bản độc lập cho từng phân vùng thực thể (DAG Node)."""

    __tablename__ = "glhs_entity_version_partitions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=False
    )
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    semantic_key: Mapped[str] = mapped_column(String(255), nullable=False)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False, default="commitloop.v1")
    consent_version: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("profile_id", "domain", "semantic_key", name="uq_glhs_partition_key"),
        Index("ix_glhs_partition_lookup", "profile_id", "domain", "semantic_key"),
    )


class GlhsInferenceContextBinding(Base):
    """Ràng buộc dòng dõi bất biến giữa snapshot THSS và suy luận của mô hình."""

    __tablename__ = "glhs_inference_context_bindings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid4()))
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=False)
    source_snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_ids_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    base_state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    consent_version: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    task: Mapped[str] = mapped_column(String(128), nullable=False)
    model_manifest_id: Mapped[str] = mapped_column(String(128), nullable=False)
    model_manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")

    __table_args__ = (
        Index("ix_glhs_binding_profile_snapshot", "profile_id", "source_snapshot_id"),
        Index("ix_glhs_binding_public_id", "public_id"),
    )


class GlhsClinicalCommitment(Base):
    """Cam kết lâm sàng theo dõi tương lai (Future-Oriented Clinical Commitment)."""

    __tablename__ = "glhs_clinical_commitments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid4()))
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=False)
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    semantic_key: Mapped[str] = mapped_column(String(255), nullable=False)
    supersession_key: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("profile_id", "semantic_key", name="uq_glhs_commitment_semantic_key"),
        Index("ix_glhs_commitment_lookup", "profile_id", "domain", "semantic_key"),
    )


class GlhsClinicalCommitmentVersion(Base):
    """Phiên bản bất biến của cam kết lâm sàng."""

    __tablename__ = "glhs_clinical_commitment_versions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid4()))
    commitment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("glhs_clinical_commitments.id", ondelete="CASCADE"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(String(32), nullable=False) # OPEN, SATISFIED, CANCELLED, SUPERSEDED
    evidence_state: Mapped[str] = mapped_column(String(32), nullable=False)  # CLEAR, CONFLICTED, INSUFFICIENT
    timeliness_state: Mapped[str] = mapped_column(String(32), nullable=False)# BEFORE_DUE, GRACE_PERIOD, OVERDUE
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    dependencies_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    fulfillment_predicate_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    cancellation_predicate_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    anchor_valid_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    anchor_known_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state_effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grace_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("commitment_id", "version_no", name="uq_glhs_commitment_version_no"),
        Index("ix_glhs_version_lookup", "commitment_id", "version_no"),
    )


class GlhsClinicalCommitmentTransition(Base):
    """Ghi nhận giao dịch chuyển trạng thái cam kết bền vững (GST Audit Trail)."""

    __tablename__ = "glhs_clinical_commitment_transitions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid4()))
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=False)
    commitment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("glhs_clinical_commitments.id", ondelete="CASCADE"), nullable=False)
    result_version_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("glhs_clinical_commitment_versions.id"), nullable=False)
    base_state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    resulting_state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    transition_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_ids_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    inference_context_binding_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("glhs_inference_context_bindings.id"), nullable=False)
    root_proposal_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index("ix_glhs_trans_bitemporal", "profile_id", "valid_at", "known_at"),
        Index("ix_glhs_trans_idempotency", "profile_id", "idempotency_key_hash"),
    )
```

---

## 2. ĐẶC TẢ ĐỘNG CƠ VỊ TỪ VÀ DSL LÂM SÀNG (PREDICATE ENGINE & AST)

### 2.1. Cú pháp Trừu tượng (Abstract Syntax Tree - AST)
Ngôn ngữ vị từ lâm sàng được định nghĩa trong `services/api/src/clara_api/glhs/predicate_dsl.py`:

```python
# Cấu trúc AST JSON Schema cho Fulfillment Predicate
{
  "op": "event",
  "equals": {
    "resource_type": "Observation",
    "system": "http://loinc.org",
    "code": "4548-4",
    "status": "final"
  },
  "value_range": {
    "comparator": ">=",
    "value": 7.0,
    "unit": "%"
  },
  "temporal_constraint": {
    "after": "anchor_valid_time",
    "before": "due_time"
  }
}
```

### 2.2. Thuật toán So khớp Tất định (Deterministic Evaluation Logic)
```python
def evaluate_predicate_ast(
    predicate: dict[str, Any],
    events: list[dict[str, Any]],
    *,
    anchor_valid_time: datetime,
    due_time: datetime | None,
    grace_end: datetime | None,
    valid_cutoff: datetime,
    known_cutoff: datetime,
) -> tuple[bool, list[str], dict[str, Any] | None]:
    """Đánh giá vị từ lâm sàng trên tập sự kiện visible theo thời gian hai chiều.
    
    Trả về: (matched: bool, matched_event_ids: list[str], decisive_event: dict | None)
    """
    matched_ids: list[str] = []
    decisive_event: dict[str, Any] | None = None

    for event in sorted(events, key=lambda x: (x["valid_at"], x["known_at"])):
        # 1. Bitemporal filter
        if event["valid_at"] > valid_cutoff or event["known_at"] > known_cutoff:
            continue
        
        # 2. Resource type & Code match
        if event["resource_type"] != predicate["equals"]["resource_type"]:
            continue
        if (event["system"], event["code"]) != (predicate["equals"]["system"], predicate["equals"]["code"]):
            continue
        if event.get("status") != predicate["equals"].get("status", "final"):
            continue
            
        # 3. Temporal window check
        if event["valid_at"] < anchor_valid_time:
            continue
            
        # Match found
        matched_ids.append(event["evidence_id"])
        decisive_event = event
        break # First decisive fulfillment event in chronology

    return bool(matched_ids), matched_ids, decisive_event
```

---

## 3. ĐẶC TẢ REST API ENDPOINTS (STRICT PYDANTIC v2 CONTRACTS)

### 3.1. `POST /api/v1/commitments/propose`
Tạo đề xuất can thiệp mới có ràng buộc snapshot bắt buộc.

* **Request Body Schema (`CommitmentProposalRequest`):**
```python
class CommitmentProposalRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    binding_id: UUID4 = Field(..., description="Public ID của GlhsInferenceContextBinding đã cấp ở bước THSS")
    target_semantic_key: str = Field(..., max_length=255, pattern=r"^[a-z0-9_\-\.:]+$")
    domain: str = Field(..., max_length=64)
    proposed_transition: Literal["OPEN", "SATISFIED", "CANCELLED", "SUPERSEDED"]
    action: str = Field(..., max_length=64)
    target: dict[str, str] = Field(..., description="Mã đối tượng (system, code)")
    dependencies: list[str] = Field(default_factory=list)
    due_time: datetime | None = None
    fulfillment_predicate: dict[str, Any] = Field(...)
    origin: Literal["model", "user", "clinician"] = "model"
```

* **Response Schema (`CommitmentProposalResponse`):**
```python
class CommitmentProposalResponse(BaseModel):
    proposal_id: UUID4
    binding_id: UUID4
    status: Literal["PENDING_REVIEW", "READY_FOR_COMMIT"]
    expected_state_version: int
    created_at: datetime
```

### 3.2. `POST /api/v1/commitments/commit`
Thực thi cổng GST và ghi bền vững xuống PostgreSQL.

* **Request Body Schema (`CommitmentCommitRequest`):**
```python
class CommitmentCommitRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    proposal_id: UUID4 = Field(..., description="ID của proposal đã được thẩm định")
    idempotency_key: str = Field(..., min_length=16, max_length=128)
    reason_code: str = Field(..., max_length=64)
```

* **Response Schema (`CommitmentCommitResponse`):**
```python
class CommitmentCommitResponse(BaseModel):
    transition_id: UUID4
    commitment_id: UUID4
    lifecycle_state: str
    resulting_state_version: int
    algorithm_digest: str
    committed_at: datetime
```

---

## 4. XỬ LÝ LỖI FAIL-CLOSED & TAXONOMY LOG GIÁM SÁT (ERROR TAXONOMY)

| Mã Lỗi Hệ Thống | HTTP Code | Điều Kiện Kích Hoạt | Hành Động Xử Lý |
| :--- | :---: | :--- | :--- |
| `GLHS_BINDING_MISSING` | `400` | Request thiếu `binding_id` hoặc `binding_id` không tồn tại | Từ chối tạo Proposal |
| `GLHS_BINDING_EXPIRED` | `410` | Snapshot THSS đã quá thời gian `expires_at` | Yêu cầu biên dịch lại THSS |
| `GLHS_STALE_PARTITION_VERSION` | `409` | Phiên bản phân vùng DAG đã bị luồng khác thay đổi | Rollback, gợi ý client retry |
| `GLHS_CONSENT_REVOKED` | `403` | Bệnh nhân đã rút consent trước khi commit | Hủy bỏ giao dịch vĩnh viễn |
| `GLHS_LINEAGE_TAMPERED` | `422` | Root proposal digest không khớp với Merkle hash | Cảnh báo bảo mật, ghi audit log |
| `GLHS_PREDICATE_CONFLICT` | `409` | Phát hiện quan sát mâu thuẫn (`contradicts`) | Chuyển sang trạng thái `CONFLICTED` |
