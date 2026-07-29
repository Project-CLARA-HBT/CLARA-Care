"""Model-neutral, draft-only multimodal extraction boundary for LifeMap."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

Modality = Literal["text", "audio", "document", "medication_label", "image"]
LocatorKind = Literal["text_offset", "timestamp", "page_region"]
Backend = Callable[["AuthorizedArtifact", "ExtractionSchema"], Awaitable[dict[str, Any]]]

_INJECTION = re.compile(
    r"(ignore (all |the )?(previous|prior) instructions|system prompt|"
    r"developer message|bo qua (moi |tat ca )?(chi dan|huong dan))",
    re.IGNORECASE,
)
_ALLOWED_UNITS = frozenset(
    {"", "mg", "g", "mcg", "ml", "l", "mmol/l", "mg/dl", "bpm", "mmhg", "°c", "%"}
)


class ExtractionRejected(ValueError):
    """Fail-closed extraction boundary violation."""


@dataclass(frozen=True)
class AuthorizedArtifact:
    artifact_id: str
    profile_partition: str
    modality: Modality
    content: bytes
    checksum_sha256: str
    locale: str = "vi"

    def verify(self) -> None:
        actual = hashlib.sha256(self.content).hexdigest()
        if not self.artifact_id or not self.profile_partition:
            raise ExtractionRejected("authorization_context_required")
        if actual != self.checksum_sha256:
            raise ExtractionRejected("artifact_checksum_mismatch")


@dataclass(frozen=True)
class ExtractionSchema:
    schema_id: str
    allowed_fields: frozenset[str]
    required_fields: frozenset[str]
    allowed_modalities: frozenset[Modality]
    diagnostic_image_interpretation: bool = False

    def validate(self) -> None:
        if not self.schema_id or not self.allowed_fields:
            raise ExtractionRejected("schema_invalid")
        if not self.required_fields <= self.allowed_fields:
            raise ExtractionRejected("required_field_not_allowed")
        if self.diagnostic_image_interpretation:
            raise ExtractionRejected("diagnostic_image_interpretation_unsupported")


@dataclass(frozen=True)
class ExtractionCandidate:
    field_path: str
    value: Any
    confidence: float
    missing: bool
    ambiguous: bool
    unit: str
    locator_kind: LocatorKind
    locator: dict[str, Any]
    model_ref: str
    status: Literal["draft"] = "draft"

    def as_dict(self) -> dict[str, Any]:
        return {
            "field_path": self.field_path,
            "value": self.value,
            "confidence": self.confidence,
            "missing": self.missing,
            "ambiguous": self.ambiguous,
            "unit": self.unit,
            "source_span": {
                "kind": self.locator_kind,
                **self.locator,
            },
            "model_ref": self.model_ref,
            "status": self.status,
        }


@dataclass(frozen=True)
class ExtractionResult:
    artifact_id: str
    artifact_checksum: str
    schema_id: str
    extractor_ref: str
    candidates: tuple[ExtractionCandidate, ...]
    missing_required_fields: tuple[str, ...]
    security_findings: tuple[str, ...]
    degraded: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_checksum": self.artifact_checksum,
            "schema_id": self.schema_id,
            "extractor_ref": self.extractor_ref,
            "candidates": [candidate.as_dict() for candidate in self.candidates],
            "missing_required_fields": list(self.missing_required_fields),
            "security_findings": list(self.security_findings),
            "degraded": self.degraded,
            "draft_only": True,
        }


class LifeMapExtractor(Protocol):
    async def extract(
        self,
        artifact: AuthorizedArtifact,
        schema: ExtractionSchema,
    ) -> ExtractionResult: ...


def _locator(raw: Any) -> tuple[LocatorKind, dict[str, Any]]:
    if not isinstance(raw, dict):
        raise ExtractionRejected("source_span_required")
    kind = raw.get("kind")
    if kind == "text_offset":
        start, end = raw.get("start"), raw.get("end")
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
            raise ExtractionRejected("text_offset_invalid")
        return "text_offset", {"start": start, "end": end}
    if kind == "timestamp":
        start, end = raw.get("start_ms"), raw.get("end_ms")
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
            raise ExtractionRejected("timestamp_invalid")
        return "timestamp", {"start_ms": start, "end_ms": end}
    if kind == "page_region":
        page, box = raw.get("page"), raw.get("box")
        if (
            not isinstance(page, int)
            or page < 1
            or not isinstance(box, list)
            or len(box) != 4
            or any(not isinstance(value, int | float) for value in box)
            or any(
                isinstance(value, bool)
                or not math.isfinite(float(value))
                or float(value) < 0
                for value in box
            )
            or float(box[2]) <= float(box[0])
            or float(box[3]) <= float(box[1])
        ):
            raise ExtractionRejected("page_region_invalid")
        return "page_region", {"page": page, "box": box}
    raise ExtractionRejected("source_span_kind_invalid")


def validate_backend_output(
    raw: dict[str, Any],
    *,
    artifact: AuthorizedArtifact,
    schema: ExtractionSchema,
    extractor_ref: str,
) -> ExtractionResult:
    artifact.verify()
    schema.validate()
    if artifact.modality not in schema.allowed_modalities:
        raise ExtractionRejected("modality_not_allowed")
    if artifact.modality == "image" and schema.diagnostic_image_interpretation:
        raise ExtractionRejected("diagnostic_image_interpretation_unsupported")
    if raw.get("artifact_checksum") != artifact.checksum_sha256:
        raise ExtractionRejected("backend_checksum_mismatch")
    raw_candidates = raw.get("candidates")
    if not isinstance(raw_candidates, list):
        raise ExtractionRejected("candidates_schema_invalid")

    raw_findings = raw.get("security_findings", [])
    if (
        not isinstance(raw_findings, list)
        or any(
            finding
            not in {"prompt_injection_source", "prompt_injection_candidate"}
            for finding in raw_findings
        )
    ):
        raise ExtractionRejected("security_findings_invalid")
    findings: set[str] = set(raw_findings)
    candidates: list[ExtractionCandidate] = []
    seen_fields: set[str] = set()
    for item in raw_candidates:
        if not isinstance(item, dict):
            raise ExtractionRejected("candidate_schema_invalid")
        field = item.get("field_path")
        if not isinstance(field, str) or field not in schema.allowed_fields:
            raise ExtractionRejected("candidate_field_not_allowed")
        confidence = item.get("confidence")
        if not isinstance(confidence, int | float) or isinstance(confidence, bool):
            raise ExtractionRejected("confidence_invalid")
        confidence = float(confidence)
        if not math.isfinite(confidence) or confidence < 0 or confidence > 1:
            raise ExtractionRejected("confidence_invalid")
        unit = str(item.get("unit") or "").strip().casefold()
        if unit not in _ALLOWED_UNITS:
            raise ExtractionRejected("unit_not_allowed")
        value = item.get("value")
        if isinstance(value, str) and _INJECTION.search(value):
            findings.add("prompt_injection_candidate")
            continue
        locator_kind, locator = _locator(item.get("source_span"))
        if locator_kind == "text_offset":
            try:
                source_text = artifact.content.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ExtractionRejected("text_artifact_encoding_invalid") from error
            if int(locator["end"]) > len(source_text):
                raise ExtractionRejected("text_offset_outside_artifact")
        candidate = ExtractionCandidate(
            field_path=field,
            value=value,
            confidence=confidence,
            missing=bool(item.get("missing", False)),
            ambiguous=bool(item.get("ambiguous", False)),
            unit=unit,
            locator_kind=locator_kind,
            locator=locator,
            model_ref=str(item.get("model_ref") or extractor_ref),
        )
        candidates.append(candidate)
        if not candidate.missing:
            seen_fields.add(field)

    missing = tuple(sorted(schema.required_fields - seen_fields))
    return ExtractionResult(
        artifact_id=artifact.artifact_id,
        artifact_checksum=artifact.checksum_sha256,
        schema_id=schema.schema_id,
        extractor_ref=extractor_ref,
        candidates=tuple(candidates),
        missing_required_fields=missing,
        security_findings=tuple(sorted(findings)),
        degraded=bool(raw.get("degraded", False)) or bool(missing),
    )


class ValidatedAdapter:
    """Adapter shared by current OCR/ASR/layout/DeepSeek and optional VLM paths."""

    def __init__(
        self,
        *,
        extractor_ref: str,
        supported_modalities: frozenset[Modality],
        backend: Backend,
    ) -> None:
        self.extractor_ref = extractor_ref
        self.supported_modalities = supported_modalities
        self.backend = backend

    async def extract(
        self,
        artifact: AuthorizedArtifact,
        schema: ExtractionSchema,
    ) -> ExtractionResult:
        if artifact.modality not in self.supported_modalities:
            raise ExtractionRejected("adapter_modality_unsupported")
        raw = await self.backend(artifact, schema)
        if not isinstance(raw, dict):
            raise ExtractionRejected("backend_output_invalid")
        return validate_backend_output(
            raw,
            artifact=artifact,
            schema=schema,
            extractor_ref=self.extractor_ref,
        )


def current_adapters(
    *,
    ocr_backend: Backend,
    asr_backend: Backend,
    layout_backend: Backend,
    deepseek_backend: Backend,
    vlm_backend: Backend | None = None,
) -> dict[str, LifeMapExtractor]:
    adapters: dict[str, LifeMapExtractor] = {
        "ocr": ValidatedAdapter(
            extractor_ref="current-ocr-bridge",
            supported_modalities=frozenset({"medication_label", "document"}),
            backend=ocr_backend,
        ),
        "asr": ValidatedAdapter(
            extractor_ref="current-asr-composition",
            supported_modalities=frozenset({"audio"}),
            backend=asr_backend,
        ),
        "layout": ValidatedAdapter(
            extractor_ref="document-layout-ocr",
            supported_modalities=frozenset({"document"}),
            backend=layout_backend,
        ),
        "deepseek": ValidatedAdapter(
            extractor_ref="deepseek-structured-extraction",
            supported_modalities=frozenset({"text"}),
            backend=deepseek_backend,
        ),
    }
    if vlm_backend is not None:
        adapters["vlm_candidate"] = ValidatedAdapter(
            extractor_ref="optional-vlm-candidate",
            supported_modalities=frozenset({"image", "document", "medication_label"}),
            backend=vlm_backend,
        )
    return adapters
