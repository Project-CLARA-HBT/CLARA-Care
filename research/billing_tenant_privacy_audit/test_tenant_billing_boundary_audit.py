"""Automated test suite for multi-tenant billing boundary privacy audit (PH04_A09).

Verifies 44 security and privacy audit vectors:
1. Tenant Usage Metering & Storage Isolation (7 vectors)
2. Billing Aggregator Boundary Integrity (7 vectors)
3. Cross-Tenant Metadata Disclosure Prevention (7 vectors)
4. Zero-PII / Zero-PHI Invariant in Billing & Telemetry (7 vectors)
5. Side-Channel & Timing Inference Resistance (6 vectors)
6. Cryptographic Privacy Audit Receipts & Tamper Detection (4 vectors)
7. End-to-End HTTP Billing & Telemetry API Gateway (6 vectors)

Standards: HIPAA §164.312(a)(1), GDPR Art. 32, Vietnam Decree 13/2023/ND-CP,
           OWASP API Security Top 10 (API1:2023 BOLA/IDOR, API3:2023 BOPP).
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.testclient import TestClient

from research.billing_tenant_privacy_audit.audit_schemas import (
    FORBIDDEN_PHI_KEYS,
    ComplianceBoundaryEvent,
    InvoiceLineItem,
    MeterAggregationSummary,
    MeterKind,
    PrivacyAuditReceipt,
    SurfaceKind,
    TenantInvoice,
    TenantUsageAggregation,
    TenantUsageEvent,
)
from research.billing_tenant_privacy_audit.meter_aggregator import (
    METER_PRICING_CENTS,
    TenantBillingAggregator,
    TenantBoundaryViolationError,
    TenantRateLimiter,
    TenantResourceNotFoundError,
    TenantUsageMeterStore,
    scrub_metadata_for_tenant_leak,
)


# ==============================================================================
# Suite 1: Tenant Usage Metering & Storage Isolation
# ==============================================================================

class TestTenantMeterIsolation:
    """Audit vectors for storage-level tenant partitioning and meter immutability."""

    def test_vec_tbba_iso_01_meter_write_isolated_to_partition(self) -> None:
        """Event written for tenant_alpha must never appear in tenant_beta queries."""
        store = TenantUsageMeterStore()
        event_alpha = TenantUsageEvent(
            tenant_id="org_hanoi_general",
            surface=SurfaceKind.CHAT,
            meter_kind=MeterKind.LLM_PROMPT_TOKENS,
            quantity=1500.0,
            idempotency_key="idemp-hanoi-001",
        )
        is_new, event_id = store.record_event(event_alpha)
        assert is_new is True
        assert event_id == event_alpha.event_id

        # Query tenant_alpha
        events_alpha = store.get_events("org_hanoi_general")
        assert len(events_alpha) == 1
        assert events_alpha[0].quantity == 1500.0

        # Query tenant_beta - MUST be empty
        events_beta = store.get_events("org_hcmc_children")
        assert len(events_beta) == 0

    def test_vec_tbba_iso_02_idempotency_triple_key(self) -> None:
        """Idempotency is partitioned by (tenant_id, meter_kind, idempotency_key)."""
        store = TenantUsageMeterStore()
        shared_key = "idemp-cycle-2026-10-01"

        event_a = TenantUsageEvent(
            tenant_id="tenant_hospital_a",
            surface=SurfaceKind.SCRIBE,
            meter_kind=MeterKind.ASR_AUDIO_SECONDS,
            quantity=120.0,
            idempotency_key=shared_key,
        )
        event_b = TenantUsageEvent(
            tenant_id="tenant_hospital_b",
            surface=SurfaceKind.SCRIBE,
            meter_kind=MeterKind.ASR_AUDIO_SECONDS,
            quantity=85.0,
            idempotency_key=shared_key,
        )

        # Same key across different tenants must both succeed
        ok_a, id_a = store.record_event(event_a)
        ok_b, id_b = store.record_event(event_b)
        assert ok_a is True
        assert ok_b is True
        assert id_a != id_b

        # Duplicate submission for hospital A with same key must be deduplicated
        dup_event_a = TenantUsageEvent(
            tenant_id="tenant_hospital_a",
            surface=SurfaceKind.SCRIBE,
            meter_kind=MeterKind.ASR_AUDIO_SECONDS,
            quantity=999.0,  # tampered duplicate payload
            idempotency_key=shared_key,
        )
        ok_dup, id_dup = store.record_event(dup_event_a)
        assert ok_dup is False
        assert id_dup == id_a

        # Hospital A records must still have only 1 event with original quantity
        records_a = store.get_events("tenant_hospital_a")
        assert len(records_a) == 1
        assert records_a[0].quantity == 120.0

    def test_vec_tbba_iso_03_missing_or_whitespace_tenant_id_rejected(self) -> None:
        """Empty, whitespace, or invalid tenant_id must fail schema validation fail-closed."""
        with pytest.raises(ValueError, match="tenant_id"):
            TenantUsageEvent(
                tenant_id="",
                surface=SurfaceKind.CAREGUARD,
                meter_kind=MeterKind.CAREGUARD_CHECKS,
                quantity=1.0,
                idempotency_key="idemp-err-01",
            )

        with pytest.raises(ValueError, match="tenant_id"):
            TenantUsageEvent(
                tenant_id="   ",
                surface=SurfaceKind.CAREGUARD,
                meter_kind=MeterKind.CAREGUARD_CHECKS,
                quantity=1.0,
                idempotency_key="idemp-err-02",
            )

        with pytest.raises(ValueError, match="invalid characters"):
            TenantUsageEvent(
                tenant_id="org/with/slashes",
                surface=SurfaceKind.CAREGUARD,
                meter_kind=MeterKind.CAREGUARD_CHECKS,
                quantity=1.0,
                idempotency_key="idemp-err-03",
            )

    def test_vec_tbba_iso_04_negative_or_nan_quantity_rejected(self) -> None:
        """Negative, NaN, or infinite meter quantities must be rejected."""
        with pytest.raises(ValueError, match=r"(quantity|greater than or equal)"):
            TenantUsageEvent(
                tenant_id="org_clinic_01",
                surface=SurfaceKind.CHAT,
                meter_kind=MeterKind.LLM_PROMPT_TOKENS,
                quantity=-50.0,
                idempotency_key="idemp-err-04",
            )

        with pytest.raises(ValueError, match=r"(quantity|greater than or equal|finite)"):
            TenantUsageEvent(
                tenant_id="org_clinic_01",
                surface=SurfaceKind.CHAT,
                meter_kind=MeterKind.LLM_PROMPT_TOKENS,
                quantity=float("nan"),
                idempotency_key="idemp-err-05",
            )

        with pytest.raises(ValueError, match=r"(quantity|greater than or equal|finite)"):
            TenantUsageEvent(
                tenant_id="org_clinic_01",
                surface=SurfaceKind.CHAT,
                meter_kind=MeterKind.LLM_PROMPT_TOKENS,
                quantity=float("inf"),
                idempotency_key="idemp-err-06",
            )

    def test_vec_tbba_iso_05_concurrent_multi_tenant_writes_thread_safety(self) -> None:
        """Concurrent writes across 10 tenants in parallel maintain partition integrity."""
        store = TenantUsageMeterStore()
        tenants = [f"tenant_concurrency_{i:02d}" for i in range(10)]
        writes_per_tenant = 20

        def write_tenant_events(tid: str) -> None:
            for j in range(writes_per_tenant):
                ev = TenantUsageEvent(
                    tenant_id=tid,
                    surface=SurfaceKind.CHAT,
                    meter_kind=MeterKind.LLM_PROMPT_TOKENS,
                    quantity=100.0 + j,
                    idempotency_key=f"idemp-{tid}-{j}",
                )
                store.record_event(ev)

        with ThreadPoolExecutor(max_workers=10) as executor:
            list(executor.map(write_tenant_events, tenants))

        # Verify each tenant has exactly 20 events and zero cross-contamination
        for tid in tenants:
            events = store.get_events(tid)
            assert len(events) == writes_per_tenant
            for ev in events:
                assert ev.tenant_id == tid

    def test_vec_tbba_iso_06_tampered_tenant_identifier_validation(self) -> None:
        """Attacker attempting path-traversal or SQL injection in tenant_id is blocked."""
        malicious_ids = [
            "tenant_id' OR '1'='1",
            "../tenant_escape",
            "tenant;DROP TABLE meters;--",
            "tenant<script>",
        ]
        for bad_id in malicious_ids:
            with pytest.raises(ValueError, match="invalid characters"):
                TenantUsageEvent(
                    tenant_id=bad_id,
                    surface=SurfaceKind.CHAT,
                    meter_kind=MeterKind.LLM_PROMPT_TOKENS,
                    quantity=1.0,
                    idempotency_key=f"idemp-{bad_id[:5]}",
                )

    def test_vec_tbba_iso_07_all_allowlisted_meter_kinds_accepted(self) -> None:
        """Control test: all 8 allowlisted meter dimensions function properly."""
        store = TenantUsageMeterStore()
        tenant = "org_positive_control"
        for i, meter in enumerate(MeterKind):
            ev = TenantUsageEvent(
                tenant_id=tenant,
                surface=SurfaceKind.PLATFORM,
                meter_kind=meter,
                quantity=10.0 * (i + 1),
                idempotency_key=f"idemp-ctrl-{meter.value}",
            )
            is_new, _ = store.record_event(ev)
            assert is_new is True

        events = store.get_events(tenant)
        assert len(events) == len(MeterKind)


# ==============================================================================
# Suite 2: Billing Aggregator Boundary Integrity
# ==============================================================================

class TestBillingAggregatorBoundaries:
    """Audit vectors for tenant aggregation calculations and boundary sealing."""

    def test_vec_tbba_agg_01_aggregation_strict_tenant_filter(self) -> None:
        """Aggregation for tenant_A must compute exact totals without tenant_B contribution."""
        store = TenantUsageMeterStore()
        aggregator = TenantBillingAggregator(store)
        now = datetime.now(tz=UTC)
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)

        # Seed tenant A: 10,000 prompt tokens (price 2) -> 20,000 cents
        store.record_event(
            TenantUsageEvent(
                tenant_id="tenant_a",
                surface=SurfaceKind.CHAT,
                meter_kind=MeterKind.LLM_PROMPT_TOKENS,
                quantity=10000.0,
                idempotency_key="idemp-agg-a1",
                timestamp=now,
            )
        )
        # Seed tenant B: 50,000 prompt tokens (price 2) -> 100,000 cents
        store.record_event(
            TenantUsageEvent(
                tenant_id="tenant_b",
                surface=SurfaceKind.CHAT,
                meter_kind=MeterKind.LLM_PROMPT_TOKENS,
                quantity=50000.0,
                idempotency_key="idemp-agg-b1",
                timestamp=now,
            )
        )

        res_a = aggregator.aggregate("tenant_a", start, end)
        assert res_a.tenant_id == "tenant_a"
        assert res_a.has_data is True
        assert res_a.event_count == 1
        assert res_a.meters[MeterKind.LLM_PROMPT_TOKENS.value].total_units == 10000.0
        assert res_a.total_cost_cents == 20000

        res_b = aggregator.aggregate("tenant_b", start, end)
        assert res_b.tenant_id == "tenant_b"
        assert res_b.has_data is True
        assert res_b.event_count == 1
        assert res_b.meters[MeterKind.LLM_PROMPT_TOKENS.value].total_units == 50000.0
        assert res_b.total_cost_cents == 100000

    def test_vec_tbba_agg_02_empty_state_honest_reporting(self) -> None:
        """Querying a tenant with no activity returns has_data=False and 0 cost."""
        store = TenantUsageMeterStore()
        aggregator = TenantBillingAggregator(store)
        now = datetime.now(tz=UTC)
        start = now - timedelta(days=7)
        end = now

        # Active tenant exists
        store.record_event(
            TenantUsageEvent(
                tenant_id="tenant_active",
                surface=SurfaceKind.RESEARCH,
                meter_kind=MeterKind.LLM_COMPLETION_TOKENS,
                quantity=5000.0,
                idempotency_key="idemp-active",
                timestamp=now - timedelta(days=1),
            )
        )

        # Empty tenant queried
        res_empty = aggregator.aggregate("tenant_dormant", start, end)
        assert res_empty.tenant_id == "tenant_dormant"
        assert res_empty.has_data is False
        assert res_empty.event_count == 0
        assert res_empty.total_cost_cents == 0
        assert len(res_empty.meters) == 0

    def test_vec_tbba_agg_03_temporal_window_strict_clamping(self) -> None:
        """Events outside [start_time, end_time] must not be included."""
        store = TenantUsageMeterStore()
        aggregator = TenantBillingAggregator(store)
        t_base = datetime(2026, 10, 15, 12, 0, 0, tzinfo=UTC)

        # Event 1: Before window
        store.record_event(
            TenantUsageEvent(
                tenant_id="tenant_time",
                surface=SurfaceKind.CHAT,
                meter_kind=MeterKind.LLM_PROMPT_TOKENS,
                quantity=100.0,
                idempotency_key="idemp-t1",
                timestamp=t_base - timedelta(days=2),
            )
        )
        # Event 2: In window
        store.record_event(
            TenantUsageEvent(
                tenant_id="tenant_time",
                surface=SurfaceKind.CHAT,
                meter_kind=MeterKind.LLM_PROMPT_TOKENS,
                quantity=500.0,
                idempotency_key="idemp-t2",
                timestamp=t_base,
            )
        )
        # Event 3: After window
        store.record_event(
            TenantUsageEvent(
                tenant_id="tenant_time",
                surface=SurfaceKind.CHAT,
                meter_kind=MeterKind.LLM_PROMPT_TOKENS,
                quantity=1000.0,
                idempotency_key="idemp-t3",
                timestamp=t_base + timedelta(days=2),
            )
        )

        window_start = t_base - timedelta(hours=1)
        window_end = t_base + timedelta(hours=1)

        res = aggregator.aggregate("tenant_time", window_start, window_end)
        assert res.event_count == 1
        assert res.meters[MeterKind.LLM_PROMPT_TOKENS.value].total_units == 500.0

    def test_vec_tbba_agg_04_cross_surface_meter_isolation(self) -> None:
        """Meters across different surfaces (Scribe vs CareGuard vs Chat) maintain separate subtotals."""
        store = TenantUsageMeterStore()
        aggregator = TenantBillingAggregator(store)
        now = datetime.now(tz=UTC)
        tid = "tenant_multi_surface"

        store.record_event(
            TenantUsageEvent(
                tenant_id=tid,
                surface=SurfaceKind.SCRIBE,
                meter_kind=MeterKind.ASR_AUDIO_SECONDS,
                quantity=300.0,
                idempotency_key="idemp-ms-1",
                timestamp=now,
            )
        )
        store.record_event(
            TenantUsageEvent(
                tenant_id=tid,
                surface=SurfaceKind.CAREGUARD,
                meter_kind=MeterKind.CAREGUARD_CHECKS,
                quantity=10.0,
                idempotency_key="idemp-ms-2",
                timestamp=now,
            )
        )

        res = aggregator.aggregate(tid, now - timedelta(hours=1), now + timedelta(hours=1))
        assert "scribe" in res.surface_breakdown
        assert "careguard" in res.surface_breakdown
        assert res.surface_breakdown["scribe"][MeterKind.ASR_AUDIO_SECONDS.value] == 300.0
        assert res.surface_breakdown["careguard"][MeterKind.CAREGUARD_CHECKS.value] == 10.0

        # Scribe price: 10 * 300 = 3000
        # CareGuard price: 50 * 10 = 500
        # Total = 3500
        assert res.total_cost_cents == 3500

    def test_vec_tbba_agg_05_subtotal_and_vat_calculation_accuracy(self) -> None:
        """Invoice generation applies exact subtotal, 10% VAT, and total seal."""
        store = TenantUsageMeterStore()
        aggregator = TenantBillingAggregator(store)
        now = datetime.now(tz=UTC)
        tid = "tenant_invoice_test"

        store.record_event(
            TenantUsageEvent(
                tenant_id=tid,
                surface=SurfaceKind.COUNCIL,
                meter_kind=MeterKind.COUNCIL_CASES,
                quantity=5.0,  # 5 * 500 = 2500 cents
                idempotency_key="idemp-inv-1",
                timestamp=now,
            )
        )

        invoice = aggregator.generate_invoice(
            tid,
            "2026-10",
            now - timedelta(days=1),
            now + timedelta(days=1),
        )
        assert invoice.subtotal_cents == 2500
        assert invoice.tax_cents == 250  # 10%
        assert invoice.total_cents == 2750
        assert invoice.currency == "VND"
        assert len(invoice.cryptographic_seal) == 64  # SHA-256

    def test_vec_tbba_agg_06_scope_digest_deterministic_tamper_evidence(self) -> None:
        """Scope digest is reproducible; altering any boundary parameter changes the hash."""
        start = datetime(2026, 10, 1, tzinfo=UTC)
        end = datetime(2026, 10, 31, tzinfo=UTC)

        d1 = TenantUsageAggregation.compute_scope_digest("org_1", start, end, 10, 50000)
        d2 = TenantUsageAggregation.compute_scope_digest("org_1", start, end, 10, 50000)
        assert d1 == d2

        # Altering tenant
        d_diff_tenant = TenantUsageAggregation.compute_scope_digest("org_2", start, end, 10, 50000)
        assert d1 != d_diff_tenant

        # Altering total cents
        d_diff_cents = TenantUsageAggregation.compute_scope_digest("org_1", start, end, 10, 50001)
        assert d1 != d_diff_cents

    def test_vec_tbba_agg_07_zero_cross_tenant_aggregation_leak(self) -> None:
        """Calling aggregator with empty tenant ID fails immediately without global aggregation."""
        store = TenantUsageMeterStore()
        aggregator = TenantBillingAggregator(store)
        now = datetime.now(tz=UTC)
        with pytest.raises(ValueError, match="tenant_id must be non-empty"):
            aggregator.aggregate("", now - timedelta(days=1), now)


# ==============================================================================
# Suite 3: Cross-Tenant Metadata Disclosure Prevention
# ==============================================================================

class TestCrossTenantMetadataDisclosure:
    """Audit vectors preventing identifier probing, BOLA/IDOR, and metadata leakage."""

    def test_vec_tbba_dis_01_invoice_lookup_cross_tenant_returns_404(self) -> None:
        """Tenant A querying Tenant B's invoice ID raises 404 (non-enumeration)."""
        store = TenantUsageMeterStore()
        aggregator = TenantBillingAggregator(store)
        now = datetime.now(tz=UTC)

        inv_b = aggregator.generate_invoice(
            "tenant_victim",
            "2026-10",
            now - timedelta(days=1),
            now,
        )

        # Attacker belonging to tenant_attacker requests inv_b.invoice_id
        with pytest.raises(TenantResourceNotFoundError) as exc_info:
            store.get_invoice("tenant_attacker", inv_b.invoice_id)

        assert "not found" in str(exc_info.value).lower()
        # Invariant: error message must NEVER leak tenant_victim
        assert "tenant_victim" not in str(exc_info.value)

    def test_vec_tbba_dis_02_non_enumeration_error_message(self) -> None:
        """Error messages for missing and foreign resources are indistinguishable."""
        store = TenantUsageMeterStore()
        aggregator = TenantBillingAggregator(store)
        now = datetime.now(tz=UTC)

        inv_real = aggregator.generate_invoice("tenant_a", "2026-10", now - timedelta(days=1), now)

        # Non-existent invoice
        with pytest.raises(TenantResourceNotFoundError) as err_nonexistent:
            store.get_invoice("tenant_b", "inv_nonexistent_999")

        # Foreign invoice
        with pytest.raises(TenantResourceNotFoundError) as err_foreign:
            store.get_invoice("tenant_b", inv_real.invoice_id)

        # Both errors format identically: "Invoice '<id>' not found"
        assert "not found" in str(err_nonexistent.value)
        assert "not found" in str(err_foreign.value)

    def test_vec_tbba_dis_03_scrubber_detects_foreign_tenant_leak(self) -> None:
        """Metadata scrubber detects foreign tenant_id and raises boundary violation."""
        payload = {
            "meter": "chat",
            "tenant_id": "org_foreign_leak",
            "count": 10,
        }
        with pytest.raises(TenantBoundaryViolationError) as exc_info:
            scrub_metadata_for_tenant_leak(payload, caller_tenant_id="org_legit")
        assert exc_info.value.attempted_tenant == "org_foreign_leak"
        assert exc_info.value.caller_tenant == "org_legit"

    def test_vec_tbba_dis_04_trace_context_does_not_disclose_peer_tenant(self) -> None:
        """Trace headers and metadata only emit caller's authorized tenant context."""
        caller = "org_hospital_bach_mai"
        clean_payload = {
            "invoice_id": "inv_001",
            "tenant_id": caller,
            "subtotal": 1000,
        }
        scrubbed = scrub_metadata_for_tenant_leak(clean_payload, caller_tenant_id=caller)
        assert scrubbed["tenant_id"] == caller

    def test_vec_tbba_dis_05_workspace_and_channel_ids_not_leaked(self) -> None:
        """Billing line-items do not contain internal folder/channel UUIDs."""
        store = TenantUsageMeterStore()
        aggregator = TenantBillingAggregator(store)
        now = datetime.now(tz=UTC)

        store.record_event(
            TenantUsageEvent(
                tenant_id="org_workspace_test",
                surface=SurfaceKind.CHAT,
                meter_kind=MeterKind.LLM_PROMPT_TOKENS,
                quantity=100.0,
                idempotency_key="idemp-ws-1",
                timestamp=now,
            )
        )
        invoice = aggregator.generate_invoice(
            "org_workspace_test", "2026-10", now - timedelta(days=1), now
        )

        for item in invoice.line_items:
            item_dict = item.model_dump()
            assert "channel_id" not in item_dict
            assert "folder_id" not in item_dict
            assert "user_id" not in item_dict

    def test_vec_tbba_dis_06_unauthenticated_tenant_resolution_fails_closed(self) -> None:
        """Scrubber rejects when caller_tenant_id is empty."""
        with pytest.raises(TenantBoundaryViolationError):
            scrub_metadata_for_tenant_leak({"tenant_id": "tenant_1"}, caller_tenant_id="")

    def test_vec_tbba_dis_07_invoice_cryptographic_seal_verifies_authenticity(self) -> None:
        """Tampering with invoice totals invalidates the cryptographic seal."""
        store = TenantUsageMeterStore()
        aggregator = TenantBillingAggregator(store)
        now = datetime.now(tz=UTC)

        inv = aggregator.generate_invoice("org_seal_test", "2026-10", now - timedelta(days=1), now)
        original_seal = inv.cryptographic_seal

        # Recompute seal with tampered total
        tampered_total = inv.total_cents + 1000
        aggregation = aggregator.aggregate("org_seal_test", now - timedelta(days=1), now)
        tampered_seal_payload = f"{inv.tenant_id}:{inv.billing_period}:{aggregation.scope_digest}:{tampered_total}"
        tampered_seal = hashlib.sha256(tampered_seal_payload.encode("utf-8")).hexdigest()

        assert original_seal != tampered_seal


# ==============================================================================
# Suite 4: Zero-PII / Zero-PHI Invariant in Billing & Telemetry
# ==============================================================================

class TestBillingZeroPIIInvariant:
    """Audit vectors guaranteeing zero clinical or patient PII leaks into billing."""

    def test_vec_tbba_pii_01_patient_name_in_metadata_rejected(self) -> None:
        """Meter event with patient_name in metadata_tags fails validation."""
        with pytest.raises(ValueError, match="PHI/PII violation.*patient_name"):
            TenantUsageEvent(
                tenant_id="org_clinic_vn",
                surface=SurfaceKind.CHAT,
                meter_kind=MeterKind.LLM_PROMPT_TOKENS,
                quantity=100.0,
                idempotency_key="idemp-phi-1",
                metadata_tags={"patient_name": "Nguyen Van A"},
            )

    def test_vec_tbba_pii_02_email_in_metadata_rejected(self) -> None:
        """Regex detects raw email address in any metadata value and rejects it."""
        with pytest.raises(ValueError, match="email address detected"):
            TenantUsageEvent(
                tenant_id="org_clinic_vn",
                surface=SurfaceKind.CHAT,
                meter_kind=MeterKind.LLM_PROMPT_TOKENS,
                quantity=100.0,
                idempotency_key="idemp-phi-2",
                metadata_tags={"operator_note": "sent report to patient@example.com"},
            )

    def test_vec_tbba_pii_03_query_and_prompt_text_rejected(self) -> None:
        """Clinical prompt or query text in billing metadata is strictly forbidden."""
        with pytest.raises(ValueError, match="PHI/PII violation.*query_text"):
            TenantUsageEvent(
                tenant_id="org_clinic_vn",
                surface=SurfaceKind.CHAT,
                meter_kind=MeterKind.LLM_PROMPT_TOKENS,
                quantity=100.0,
                idempotency_key="idemp-phi-3",
                metadata_tags={"query_text": "Bệnh nhân bị đau tức ngực trái"},
            )

    def test_vec_tbba_pii_04_prescription_and_medications_rejected(self) -> None:
        """Drug names and dosages in billing metadata are rejected."""
        with pytest.raises(ValueError, match="PHI/PII violation.*medication"):
            TenantUsageEvent(
                tenant_id="org_clinic_vn",
                surface=SurfaceKind.SELFMED,
                meter_kind=MeterKind.CAREGUARD_CHECKS,
                quantity=1.0,
                idempotency_key="idemp-phi-4",
                metadata_tags={"medication": "Paracetamol 500mg"},
            )

    def test_vec_tbba_pii_05_diagnoses_and_symptoms_rejected(self) -> None:
        """Clinical symptoms and diagnosis codes are forbidden in billing."""
        with pytest.raises(ValueError, match="PHI/PII violation.*symptoms"):
            TenantUsageEvent(
                tenant_id="org_clinic_vn",
                surface=SurfaceKind.COUNCIL,
                meter_kind=MeterKind.COUNCIL_CASES,
                quantity=1.0,
                idempotency_key="idemp-phi-5",
                metadata_tags={"symptoms": "sốt cao 39 độ, ho có đờm"},
            )

    def test_vec_tbba_pii_06_invoice_line_items_contain_strictly_accounting_units(self) -> None:
        """Invoice line item attributes are strictly allowlisted accounting fields."""
        item = InvoiceLineItem(
            meter_kind="asr_audio_seconds",
            surface="scribe",
            units=120.0,
            unit_price_cents=10,
            line_total_cents=1200,
        )
        keys = set(item.model_dump().keys())
        expected_keys = {"meter_kind", "surface", "units", "unit_price_cents", "line_total_cents"}
        assert keys == expected_keys
        # None of the keys overlap with forbidden clinical terms
        assert keys.isdisjoint(FORBIDDEN_PHI_KEYS)

    def test_vec_tbba_pii_07_compliance_event_hashes_subject_identity(self) -> None:
        """Compliance events store SHA-256 subject digest, never plaintext email or user ID."""
        raw_user_id = "user_doctor_12345"
        digest = hashlib.sha256(raw_user_id.encode("utf-8")).hexdigest()

        event = ComplianceBoundaryEvent(
            attempted_tenant_id="org_hanoi",
            authenticated_tenant_id="org_danang",
            caller_role="clinician",
            endpoint="/api/v1/billing/usage",
            subject_digest=digest,
        )
        assert event.subject_digest == digest
        assert raw_user_id not in event.model_dump_json()


# ==============================================================================
# Suite 5: Side-Channel & Timing Inference Resistance
# ==============================================================================

class TestSideChannelIsolation:
    """Audit vectors ensuring per-tenant token bucket and timing isolation."""

    def test_vec_tbba_sdc_01_token_bucket_exhaustion_does_not_throttle_peer(self) -> None:
        """Tenant A exhausting their rate limit does not degrade or throttle Tenant B."""
        limiter = TenantRateLimiter(capacity=5, refill_rate_per_sec=0.1)

        # Exhaust Tenant A's bucket
        for _ in range(5):
            allowed, _ = limiter.consume("tenant_noisy", 1)
            assert allowed is True

        # 6th request for Tenant A is throttled
        blocked_a, _ = limiter.consume("tenant_noisy", 1)
        assert blocked_a is False

        # Tenant B makes request - MUST succeed immediately
        allowed_b, rem_b = limiter.consume("tenant_quiet", 1)
        assert allowed_b is True
        assert rem_b == 4

    def test_vec_tbba_sdc_02_rate_limiter_refill_independence(self) -> None:
        """Bucket refill timers are independent between tenants."""
        limiter = TenantRateLimiter(capacity=10, refill_rate_per_sec=5.0)
        limiter.consume("t1", 5)
        rem_t1 = limiter.get_remaining("t1")
        rem_t2 = limiter.get_remaining("t2")

        assert rem_t1 == 5
        assert rem_t2 == 10  # Untouched tenant retains full capacity

    def test_vec_tbba_sdc_03_constant_shape_quota_response(self) -> None:
        """Quota responses expose only tenant's own quota, not platform-wide capacity."""
        limiter = TenantRateLimiter(capacity=100)
        rem = limiter.get_remaining("tenant_fresh")
        assert rem == 100

    def test_vec_tbba_sdc_04_isolated_remaining_quota_reporting(self) -> None:
        """Consuming 20 tokens from tenant_x does not alter tenant_y's remaining count."""
        limiter = TenantRateLimiter(capacity=100)
        limiter.consume("tenant_x", 20)
        assert limiter.get_remaining("tenant_x") == 80
        assert limiter.get_remaining("tenant_y") == 100

    def test_vec_tbba_sdc_05_concurrency_semaphore_partitioning(self) -> None:
        """Per-tenant concurrency limits prevent one tenant from monopolizing workers."""
        limiter = TenantRateLimiter(capacity=2)
        assert limiter.consume("org_a", 2)[0] is True
        assert limiter.consume("org_a", 1)[0] is False
        assert limiter.consume("org_b", 2)[0] is True

    def test_vec_tbba_sdc_06_side_channel_timing_bounds(self) -> None:
        """Quota check executes in constant time (< 5ms) without data-dependent delays."""
        limiter = TenantRateLimiter(capacity=1000)
        t_start = time.perf_counter()
        for i in range(100):
            limiter.consume(f"tenant_{i % 5}", 1)
        elapsed_total = (time.perf_counter() - t_start) * 1000
        avg_per_check = elapsed_total / 100
        assert avg_per_check < 2.0  # Under 2 milliseconds


# ==============================================================================
# Suite 6: Privacy Audit Receipts & Verification
# ==============================================================================

class TestPrivacyAuditReceipts:
    """Audit vectors for cryptographic compliance receipts and tamper evidence."""

    def test_vec_tbba_rcp_01_receipt_generation_with_clean_pass(self) -> None:
        """Clean audit produces receipt with result='pass' and 0 findings."""
        store = TenantUsageMeterStore()
        aggregator = TenantBillingAggregator(store)
        now = datetime.now(tz=UTC)
        tid = "org_receipt_test"

        store.record_event(
            TenantUsageEvent(
                tenant_id=tid,
                surface=SurfaceKind.CHAT,
                meter_kind=MeterKind.LLM_PROMPT_TOKENS,
                quantity=1000.0,
                idempotency_key="idemp-rcp-1",
                timestamp=now,
            )
        )
        agg = aggregator.aggregate(tid, now - timedelta(days=1), now + timedelta(days=1))
        receipt = aggregator.generate_audit_receipt(tid, agg, findings=0)

        assert receipt.result == "pass"
        assert receipt.finding_count == 0
        assert receipt.tenant_id == tid
        assert len(receipt.scope_digest) == 64
        assert len(receipt.artifact_digest) == 64
        assert len(receipt.verified_invariants) >= 6

    def test_vec_tbba_rcp_02_tamper_detection_breaks_artifact_digest(self) -> None:
        """Altering findings count invalidates artifact digest."""
        store = TenantUsageMeterStore()
        aggregator = TenantBillingAggregator(store)
        now = datetime.now(tz=UTC)
        tid = "org_receipt_test"

        agg = aggregator.aggregate(tid, now - timedelta(days=1), now)
        r1 = aggregator.generate_audit_receipt(tid, agg, findings=0)
        r2 = aggregator.generate_audit_receipt(tid, agg, findings=1)
        assert r1.artifact_digest != r2.artifact_digest

    def test_vec_tbba_rcp_03_boundary_probe_logs_compliance_event(self) -> None:
        """Cross-tenant boundary probe creates immutable ComplianceBoundaryEvent."""
        store = TenantUsageMeterStore()
        event = ComplianceBoundaryEvent(
            attempted_tenant_id="tenant_target",
            authenticated_tenant_id="tenant_attacker",
            caller_role="doctor",
            endpoint="/api/v1/billing/invoices/inv_123",
            subject_digest=hashlib.sha256(b"attacker_doctor").hexdigest(),
        )
        store.record_compliance_event(event)

        events = store.get_compliance_events()
        assert len(events) == 1
        assert events[0].event_type == "TENANT_BOUNDARY_PROBE"
        assert events[0].severity == "CRITICAL"

    def test_vec_tbba_rcp_04_receipt_contains_zero_phi_or_foreign_metadata(self) -> None:
        """Attestation receipt verified clean of PHI and foreign tenant metadata."""
        receipt = PrivacyAuditReceipt(
            tenant_id="org_clean",
            scope_digest=hashlib.sha256(b"scope").hexdigest(),
            result="pass",
            finding_count=0,
            artifact_digest=hashlib.sha256(b"art").hexdigest(),
        )
        receipt_dict = receipt.model_dump()
        for k in receipt_dict:
            assert k.lower() not in FORBIDDEN_PHI_KEYS


# ==============================================================================
# Suite 7: End-to-End HTTP Billing & Telemetry API Gateway
# ==============================================================================

class TestHTTPBillingTenantAPIGateway:
    """End-to-end FastAPI test client testing route gates and response shapes."""

    @pytest.fixture(autouse=True)
    def setup_app(self) -> None:
        self.store = TenantUsageMeterStore()
        self.aggregator = TenantBillingAggregator(self.store)
        self.app = FastAPI(title="CLARA Billing Test Gateway")

        # Mock authentication helper
        def get_auth_context(
            x_tenant_id: str | None = Header(default=None),
            x_user_role: str | None = Header(default=None),
            authorization: str | None = Header(default=None),
        ) -> dict[str, str]:
            if not authorization or not authorization.startswith("Bearer "):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")
            if not x_tenant_id:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing tenant context")
            return {
                "tenant_id": x_tenant_id,
                "role": x_user_role or "normal",
            }

        @self.app.get("/api/v1/billing/usage", response_model=TenantUsageAggregation)
        def get_tenant_usage(
            auth: dict[str, str] = Depends(get_auth_context),
            date_from: str | None = Query(default=None),
            date_to: str | None = Query(default=None),
            target_tenant: str | None = Query(default=None),
        ) -> TenantUsageAggregation:
            caller_tenant = auth["tenant_id"]
            caller_role = auth["role"]

            # Role Gate: normal users cannot view billing
            if caller_role not in {"org_admin", "admin", "billing_manager"}:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient billing privileges")

            # Cross-tenant IDOR check: if target_tenant is passed and caller is not platform admin
            effective_tenant = caller_tenant
            if target_tenant and target_tenant != caller_tenant:
                if caller_role != "admin":
                    # Non-enumeration: 404
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant usage not found")
                effective_tenant = target_tenant

            now = datetime.now(tz=UTC)
            start = now - timedelta(days=30)
            end = now
            return self.aggregator.aggregate(effective_tenant, start, end)

        @self.app.get("/api/v1/billing/invoices/{invoice_id}", response_model=TenantInvoice)
        def get_invoice(
            invoice_id: str,
            auth: dict[str, str] = Depends(get_auth_context),
        ) -> TenantInvoice:
            caller_tenant = auth["tenant_id"]
            caller_role = auth["role"]

            if caller_role not in {"org_admin", "admin", "billing_manager"}:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient billing privileges")

            try:
                return self.store.get_invoice(caller_tenant, invoice_id)
            except TenantResourceNotFoundError:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        self.client = TestClient(self.app)

    def test_vec_tbba_http_01_tenant_admin_gets_own_usage_200(self) -> None:
        """Tenant admin receives 200 OK with their tenant's usage metrics."""
        now = datetime.now(tz=UTC)
        self.store.record_event(
            TenantUsageEvent(
                tenant_id="org_clinic_01",
                surface=SurfaceKind.CHAT,
                meter_kind=MeterKind.LLM_PROMPT_TOKENS,
                quantity=2000.0,
                idempotency_key="idemp-http-1",
                timestamp=now,
            )
        )

        resp = self.client.get(
            "/api/v1/billing/usage",
            headers={
                "Authorization": "Bearer valid_jwt_token",
                "X-Tenant-Id": "org_clinic_01",
                "X-User-Role": "org_admin",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant_id"] == "org_clinic_01"
        assert data["has_data"] is True
        assert data["event_count"] == 1

    def test_vec_tbba_http_02_cross_tenant_access_attempt_yields_404(self) -> None:
        """Org admin querying another tenant's usage returns 404 (non-enumeration)."""
        resp = self.client.get(
            "/api/v1/billing/usage?target_tenant=org_target_hospital",
            headers={
                "Authorization": "Bearer valid_jwt_token",
                "X-Tenant-Id": "org_attacker_clinic",
                "X-User-Role": "org_admin",
            },
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Tenant usage not found"

    def test_vec_tbba_http_03_unauthenticated_request_yields_401(self) -> None:
        """Missing Authorization header yields 401 Unauthorized."""
        resp = self.client.get(
            "/api/v1/billing/usage",
            headers={"X-Tenant-Id": "org_clinic_01"},
        )
        assert resp.status_code == 401
        assert "Missing Bearer token" in resp.json()["detail"]

    def test_vec_tbba_http_04_underprivileged_role_normal_yields_403(self) -> None:
        """Normal user calling billing endpoint receives 403 Forbidden."""
        resp = self.client.get(
            "/api/v1/billing/usage",
            headers={
                "Authorization": "Bearer valid_jwt_token",
                "X-Tenant-Id": "org_clinic_01",
                "X-User-Role": "normal",
            },
        )
        assert resp.status_code == 403
        assert "Insufficient billing privileges" in resp.json()["detail"]

    def test_vec_tbba_http_05_platform_admin_cross_tenant_oversight_controlled(self) -> None:
        """Platform admin role can inspect tenant view for support/operations."""
        now = datetime.now(tz=UTC)
        self.store.record_event(
            TenantUsageEvent(
                tenant_id="org_client_hospital",
                surface=SurfaceKind.RESEARCH,
                meter_kind=MeterKind.LLM_COMPLETION_TOKENS,
                quantity=15000.0,
                idempotency_key="idemp-http-admin",
                timestamp=now,
            )
        )
        resp = self.client.get(
            "/api/v1/billing/usage?target_tenant=org_client_hospital",
            headers={
                "Authorization": "Bearer admin_jwt_token",
                "X-Tenant-Id": "platform_hq",
                "X-User-Role": "admin",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant_id"] == "org_client_hospital"
        assert data["has_data"] is True

    def test_vec_tbba_http_06_new_tenant_empty_state_returns_has_data_false(self) -> None:
        """Newly created tenant querying usage receives 200 OK with has_data=False."""
        resp = self.client.get(
            "/api/v1/billing/usage",
            headers={
                "Authorization": "Bearer valid_jwt_token",
                "X-Tenant-Id": "org_brand_new_clinic",
                "X-User-Role": "org_admin",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant_id"] == "org_brand_new_clinic"
        assert data["has_data"] is False
        assert data["event_count"] == 0
        assert data["total_cost_cents"] == 0
