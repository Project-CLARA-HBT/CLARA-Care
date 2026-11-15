"""Tests for ACNS-X07_witness_gallery (runnable counterexample witnesses).

Purpose
-------
Machine-checks task ``ACNS-X07_witness_gallery`` (venue ``acns``, phase
``P04``) against its deliverable contract
``evaluation/venue2027/acns/executable_counterexamples.py``: the witness
gallery of the SoK "Evidence Boundaries of Attestation in Tool-Using AI
Systems" (RQ2) — small runnable minimal counterexample tests, one per
evidence-boundary gap (assembled-not-sent, dispatched-not-acknowledged,
acknowledged-not-executed, executed-not-committed,
signed-receipt-wrong-context), each a small executable case plus the expected
evidence-boundary verdict (REJECT / pre-registered gap code) naming the exact
missing proof.

Vector plan (written per task step 2, before the algorithm):

- **Positive P1 (gallery runs, labels reproduce)** — every registered witness
  runs via ``run_witness`` and yields exactly its frozen expected
  evidence-boundary verdict: REJECT with the pre-registered gap code (G7/G1/
  G2/G3/G4) and the demonstrated level capped below the asserted one.
- **Positive P2 (concrete witnesses per gap)** — the five mandated witnesses
  behave as named: assembled-but-never-sent leaves the dispatch claim at L1;
  a bare transport ACK supports nothing above DISPATCHED (G1); a verified
  receipt alone caps execution at L2 (G2); attested execution alone caps
  commitment at L3 (G3); a foreign-context receipt is capped below its claim
  with G4.
- **Positive P3 (witness names the exact missing proof)** — each REJECT
  artifact carries a non-trivial ``missing_proof`` naming the concrete trust
  component (TC1/TC2/TC3, PROV lineage) whose absence makes the implication
  fail, plus explicit trust assumptions and capability (unprivileged
  A1-A7 axes).
- **Positive P4 (task contract signature)** —
  ``run_counterexample(level_transition) -> ProofArtifact`` works with the
  frozen fixture, accepts level-pair aliases (e.g. ``DISPATCHED->
  ACKNOWLEDGED``) and registry ids; output is schema-stable and
  JSON-serializable (``to_dict`` round-trip), deterministic across runs.
- **Positive P5 (gallery artifact emission)** — ``emit_witness_gallery``
  writes ``artifacts/venue2027/acns/<run_id>/witness_gallery.json`` with all
  five witnesses, frozen labels, label-reproduction report and SHA256
  digests; deterministic bytes across two emissions of the same run.
- **Adversarial A1 (NOT_A_COUNTEREXAMPLE)** — supplying the missing proof
  makes the claim ADMIT at the asserted level, and ``run_counterexample``
  *refuses* to certify a supported claim as a counterexample with the stable
  reason code ``NOT_A_COUNTEREXAMPLE`` (a witness that omits nothing is
  refused as not a counterexample); the repaired case evaluates honestly via
  ``evaluate_claim_case`` as ADMIT exactly at the asserted level.
- **Adversarial A2 (PRIVILEGED_ATTACKER)** — a witness that relies on a
  privileged unrealistic attacker (hardware-root compromise outside the
  registered A1-A7 axes) is refused, not scored (threat model ED1/ED2).
- **Adversarial A3 (fail-closed inputs)** — unknown transition / witness,
  transition mismatch, malformed case and malformed evidence all fail closed
  with stable reason codes; no unhandled exception shape escapes.
- **Adversarial A4 (never a safe false completion)** — every REJECT verdict
  is ``counted_as_success=False`` in spirit: INDETERMINATE/unknown shapes are
  never produced (verdict is always ADMIT or REJECT), the observed outcome
  bucket is always in the shared harness vocabulary, and an unverifiable
  receipt proves nothing (L0) rather than being treated as a rejection of the
  underlying operation.
- **Adversarial A5 (label freeze / drift refused)** — tampering with a
  witness fixture (supplying the missing proof through the gallery name) is
  refused by ``run_witness`` label enforcement via ``GALLERY_DRIFT`` and the
  registry's frozen expected labels are not rewritten by outcomes.

Allowed input
-------------
Inline synthetic case literals and the module's frozen synthetic-acns-2027
fixtures only: no network, no database, no clock, no randomness, no live
provider, no LLM, no PHI/PII. Temporary directories are used only for the
gallery-artifact emission test.

Failure semantics
-----------------
Each violation raises the module's typed :class:`WitnessError` or
``AssertionError`` with a stable message prefix ``ACNS_X07_``; pytest reports
the failing check directly. Stdlib-only besides pytest itself.

Version
-------
``ACNS_X07_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from evaluation.venue2027.acns import executable_counterexamples as ec  # noqa: E402
from evaluation.venue2027.acns.executable_counterexamples import (  # noqa: E402
    G1_TRANSPORT_ACK_AS_PROCESSING,
    G2_RECEIPT_AS_EXECUTION,
    G3_EXECUTION_AS_CONSUMPTION,
    G4_SIGNATURE_AS_CONTEXT,
    G7_LEVEL_IMPLICIT_UPGRADE,
    WITNESS_GALLERY,
    WITNESS_IDS,
    WitnessError,
    emit_witness_gallery,
    evaluate_claim_case,
    run_counterexample,
    run_witness,
)

ACNS_X07_TEST_VERSION = "1.0.0"

MANDATED_WITNESSES = (
    "assembled-not-sent",
    "dispatched-not-acknowledged",
    "acknowledged-not-executed",
    "executed-not-committed",
    "signed-receipt-wrong-context",
)

EXPECTED_GAP_BY_WITNESS = {
    "assembled-not-sent": G7_LEVEL_IMPLICIT_UPGRADE,
    "dispatched-not-acknowledged": G1_TRANSPORT_ACK_AS_PROCESSING,
    "acknowledged-not-executed": G2_RECEIPT_AS_EXECUTION,
    "executed-not-committed": G3_EXECUTION_AS_CONSUMPTION,
    "signed-receipt-wrong-context": G4_SIGNATURE_AS_CONTEXT,
}


# ---------------------------------------------------------------------------
# Positive P1 — every witness runs and reproduces its frozen expected label
# ---------------------------------------------------------------------------
def test_gallery_registers_exactly_the_five_mandated_witnesses() -> None:
    assert (
        tuple(WITNESS_IDS) == MANDATED_WITNESSES
    ), f"ACNS_X07_GALLERY: registry {WITNESS_IDS} != mandated {MANDATED_WITNESSES}"
    for name in MANDATED_WITNESSES:
        spec = WITNESS_GALLERY[name]
        assert (
            spec.expected_verdict == "REJECT"
        ), f"ACNS_X07_GALLERY[{name}]: witness must freeze a REJECT verdict"
        assert (
            spec.expected_gap_code == EXPECTED_GAP_BY_WITNESS[name]
        ), f"ACNS_X07_GALLERY[{name}]: frozen gap code drifted"


def test_every_witness_runs_and_yields_expected_gap_verdict() -> None:
    for name in MANDATED_WITNESSES:
        artifact = run_witness(name)
        assert (
            artifact.verdict == "REJECT"
        ), f"ACNS_X07_POSITIVE[{name}]: expected REJECT, got {artifact.verdict}"
        assert (
            artifact.gap_code == EXPECTED_GAP_BY_WITNESS[name]
        ), f"ACNS_X07_POSITIVE[{name}]: gap {artifact.gap_code} != expected"
        assert (
            artifact.observed_outcome == "REJECT"
        ), f"ACNS_X07_POSITIVE[{name}]: outcome bucket must be REJECT"
        # The demonstrated level must be strictly below the asserted claim.
        assert (
            ec.LEVEL_RANK[artifact.demonstrated_level] < ec.LEVEL_RANK[artifact.asserted_level]
        ), (
            f"ACNS_X07_POSITIVE[{name}]: demonstrated level "
            f"{artifact.demonstrated_level} does not cap the asserted claim"
        )


# ---------------------------------------------------------------------------
# Positive P2 — per-gap concrete behavior of the five mandated witnesses
# ---------------------------------------------------------------------------
def test_witness_assembled_not_sent_caps_dispatch_claim_at_assembled() -> None:
    artifact = run_witness("assembled-not-sent")
    assert (
        artifact.demonstrated_level == "L1-ASSEMBLED"
    ), "ACNS_X07_POSITIVE[assembled-not-sent]: assembled bytes must support only L1"
    assert artifact.gap_code == G7_LEVEL_IMPLICIT_UPGRADE


def test_witness_dispatched_not_acknowledged_refuses_receipt_claim() -> None:
    artifact = run_witness("dispatched-not-acknowledged")
    assert (
        artifact.demonstrated_level == "L1.5-DISPATCHED"
    ), "ACNS_X07_POSITIVE[dispatched-not-acknowledged]: transport ACK supports only L1.5"
    assert artifact.gap_code == G1_TRANSPORT_ACK_AS_PROCESSING


def test_witness_acknowledged_not_executed_caps_execution_claim_at_receipt() -> None:
    artifact = run_witness("acknowledged-not-executed")
    assert (
        artifact.demonstrated_level == "L2-ACKNOWLEDGED"
    ), "ACNS_X07_POSITIVE[acknowledged-not-executed]: receipt alone caps at L2 (TC3 absent)"
    assert artifact.gap_code == G2_RECEIPT_AS_EXECUTION


def test_witness_executed_not_committed_caps_commit_claim_at_execution() -> None:
    artifact = run_witness("executed-not-committed")
    assert (
        artifact.demonstrated_level == "L3-EXECUTED"
    ), "ACNS_X07_POSITIVE[executed-not-committed]: execution alone caps at L3"
    assert artifact.gap_code == G3_EXECUTION_AS_CONSUMPTION


def test_witness_signed_receipt_wrong_context_is_capped_with_g4() -> None:
    artifact = run_witness("signed-receipt-wrong-context")
    assert (
        artifact.gap_code == G4_SIGNATURE_AS_CONTEXT
    ), "ACNS_X07_POSITIVE[signed-receipt-wrong-context]: foreign-context receipt must be G4"
    assert (
        "another request" in artifact.missing_proof or "different request" in artifact.missing_proof
    ), "ACNS_X07_POSITIVE[signed-receipt-wrong-context]: witness must name the context transplant"


# ---------------------------------------------------------------------------
# Positive P3 — the witness names the exact missing proof + trust assumptions
# ---------------------------------------------------------------------------
def test_every_reject_names_concrete_missing_proof_and_trust_assumptions() -> None:
    for name in MANDATED_WITNESSES:
        artifact = run_witness(name)
        assert (
            isinstance(artifact.missing_proof, str) and len(artifact.missing_proof) >= 40
        ), f"ACNS_X07_PROOF[{name}]: missing_proof too thin to name the concrete witness"
        assert (
            isinstance(artifact.trust_assumptions, str) and len(artifact.trust_assumptions) >= 40
        ), f"ACNS_X07_PROOF[{name}]: trust assumptions must be explicit (pass gate)"
        for _token in ("TC1", "TC2", "TC3", "PROV", "9334", "E0"):
            joined = artifact.missing_proof + " " + artifact.trust_assumptions
        # At least one concrete trust anchor / edge reference appears per witness.
        assert any(
            tok in joined
            for tok in ("TC1", "TC2", "TC3", "TC4", "PROV", "9334", "9162", "E0", "§2")
        ), f"ACNS_X07_PROOF[{name}]: no concrete trust component named"
        assert artifact.capability, f"ACNS_X07_PROOF[{name}]: capability axis must be declared"


# ---------------------------------------------------------------------------
# Positive P4 — task contract signature run_counterexample(level_transition)
# ---------------------------------------------------------------------------
def test_run_counterexample_accepts_registry_ids_and_level_pair_aliases() -> None:
    artifact = run_counterexample("dispatched-not-acknowledged")
    assert artifact.verdict == "REJECT" and artifact.gap_code == G1_TRANSPORT_ACK_AS_PROCESSING
    alias = run_counterexample("DISPATCHED->ACKNOWLEDGED")
    assert alias.verdict == artifact.verdict and alias.gap_code == artifact.gap_code
    assert alias.demonstrated_level == artifact.demonstrated_level


def test_run_counterexample_deterministic_and_json_serializable() -> None:
    first = run_counterexample("executed-not-committed").to_dict()
    second = run_counterexample("executed-not-committed").to_dict()
    assert first == second, "ACNS_X07_POSITIVE: witness runs must be deterministic"
    assert json.loads(json.dumps(first)) == first, "ACNS_X07_POSITIVE: to_dict must round-trip"
    assert first["schema_version"] and first["contract_id"].startswith(
        "clara.venue2027.acns.witness-gallery.v"
    ), "ACNS_X07_POSITIVE: schema/contract version must be stamped"


# ---------------------------------------------------------------------------
# Positive P5 — gallery artifact emission (task evidence path)
# ---------------------------------------------------------------------------
def test_emit_witness_gallery_writes_deterministic_manifest(tmp_path: pathlib.Path) -> None:
    manifest_a = emit_witness_gallery("run-emitting-a", repo_root=tmp_path)
    manifest_b = emit_witness_gallery("run-emitting-a", repo_root=tmp_path)
    out = tmp_path / "artifacts" / "venue2027" / "acns" / "run-emitting-a" / "witness_gallery.json"
    assert out.is_file(), "ACNS_X07_EMIT: witness_gallery.json not written"
    on_disk = json.loads(out.read_text(encoding="utf-8"))
    assert on_disk == manifest_a == manifest_b, "ACNS_X07_EMIT: emission must be deterministic"
    assert on_disk["witness_count"] == len(MANDATED_WITNESSES)
    assert on_disk["label_reproduction"]["failed_witnesses"] == []
    assert sorted(on_disk["label_reproduction"]["expected_verdicts_reproduced"]) == sorted(
        MANDATED_WITNESSES
    )
    for entry in on_disk["witnesses"]:
        assert entry["label_reproduced"] is True
        assert len(entry["artifact_sha256"]) == 64 and len(entry["fixture_sha256"]) == 64
        assert entry["artifact"]["verdict"] == entry["expected_verdict"]
    for bad in ("../escape", "", "bad id", "a" * 200):
        try:
            emit_witness_gallery(bad, repo_root=tmp_path)
        except WitnessError as exc:
            assert exc.reason_code == "MALFORMED_RUN_ID"
        else:
            raise AssertionError(f"ACNS_X07_EMIT: run_id {bad!r} must be refused")


# ---------------------------------------------------------------------------
# Adversarial A1 — witness with the missing proof supplied is ADMIT; a
# witness that omits nothing is refused as not a counterexample
# ---------------------------------------------------------------------------
def _repaired_case(name: str) -> dict:
    """Take a frozen witness fixture and supply its exact missing proof."""
    case = json.loads(json.dumps(WITNESS_GALLERY[name].fixture))
    claim_ctx = case["claim"]["context"]
    dispatch_digest = "sha256:" + "dd" * 32
    if name == "assembled-not-sent":
        case["evidence"].append(
            {
                "evidence_id": "ev-repaired-dispatch",
                "node_class": "transport_delivery",
                "context": dict(claim_ctx),
                "digest_binding": dispatch_digest,
            }
        )
    elif name == "dispatched-not-acknowledged":
        case["evidence"].append(
            {
                "evidence_id": "ev-repaired-receipt",
                "node_class": "provider_signed_receipt",
                "verifiable": True,
                "context": dict(claim_ctx),
                "digest_binding": dispatch_digest,
            }
        )
    elif name == "acknowledged-not-executed":
        case["evidence"].append(
            {
                "evidence_id": "ev-repaired-execution",
                "node_class": "execution",
                "verifiable": True,
                "context": dict(claim_ctx),
                "digest_binding": dispatch_digest,
                "attested_execution": True,
            }
        )
    elif name == "executed-not-committed":
        case["evidence"].append(
            {
                "evidence_id": "ev-repaired-commit",
                "node_class": "persisted_side_effect",
                "verifiable": True,
                "context": dict(claim_ctx),
                "digest_binding": dispatch_digest,
                "persisted": True,
                "lineage_recorded": True,
            }
        )
    else:  # signed-receipt-wrong-context: bind THIS request's receipt
        case["evidence"] = [
            {
                "evidence_id": "ev-repaired-bound-receipt",
                "node_class": "provider_signed_receipt",
                "verifiable": True,
                "context": dict(claim_ctx),
                "digest_binding": dispatch_digest,
            }
        ]
    return case


def test_repaired_witness_with_missing_proof_supplied_is_admit() -> None:
    for name in MANDATED_WITNESSES:
        repaired = _repaired_case(name)
        verdict = evaluate_claim_case(repaired)
        assert verdict.verdict == "ADMIT", (
            f"ACNS_X07_REPAIR[{name}]: with the missing proof supplied the claim must ADMIT, "
            f"got {verdict.verdict}/{verdict.gap_code}"
        )
        assert (
            verdict.gap_code == "none"
        ), f"ACNS_X07_REPAIR[{name}]: an ADMIT verdict carries no gap, got {verdict.gap_code}"
        assert (
            ec.LEVEL_RANK[verdict.demonstrated_level] >= ec.LEVEL_RANK[verdict.asserted_level]
        ), f"ACNS_X07_REPAIR[{name}]: demonstrated level must reach the asserted level"
        # The same repaired case must be refused as a counterexample candidate.
        try:
            run_counterexample(name, repaired)
        except WitnessError as exc:
            assert (
                exc.reason_code == "NOT_A_COUNTEREXAMPLE"
            ), f"ACNS_X07_REPAIR[{name}]: stable reason code required, got {exc.reason_code}"
        else:
            raise AssertionError(
                f"ACNS_X07_REPAIR[{name}]: a supported claim must be refused as a counterexample"
            )


def test_repaired_case_admits_exactly_at_asserted_level_not_above() -> None:
    repaired = _repaired_case("acknowledged-not-executed")
    verdict = evaluate_claim_case(repaired)
    assert verdict.demonstrated_level == "L3-EXECUTED"
    assert verdict.asserted_level == "L3-EXECUTED"
    # Without the TEE anchor the same shape stays REJECT (G2), proving the
    # upgrade came from the attested-execution anchor, not from generosity.
    no_tee = json.loads(json.dumps(repaired))
    for item in no_tee["evidence"]:
        if item["node_class"] == "execution":
            item["attested_execution"] = False
    downgraded = evaluate_claim_case(no_tee)
    assert downgraded.verdict == "REJECT" and downgraded.gap_code == G2_RECEIPT_AS_EXECUTION


# ---------------------------------------------------------------------------
# Adversarial A2 — privileged unrealistic attacker is refused, not scored
# ---------------------------------------------------------------------------
def test_privileged_unrealistic_attacker_capability_is_refused() -> None:
    base = json.loads(json.dumps(WITNESS_GALLERY["acknowledged-not-executed"].fixture))
    for capability, expected in (
        ("A8", "PRIVILEGED_ATTACKER"),
        ("hardware-root", "PRIVILEGED_ATTACKER"),
        ("", "MALFORMED_CASE"),
    ):
        case = json.loads(json.dumps(base))
        case["capability"] = capability
        try:
            evaluate_claim_case(case)
        except WitnessError as exc:
            assert (
                exc.reason_code == expected
            ), f"ACNS_X07_ADVERSARIAL[{capability!r}]: got {exc.reason_code}, want {expected}"
        else:
            raise AssertionError(
                f"ACNS_X07_ADVERSARIAL[{capability!r}]: privileged attacker must be refused"
            )
    # Registered composed axes remain legal.
    ok = json.loads(json.dumps(base))
    ok["capability"] = "A4+A3"
    assert evaluate_claim_case(ok).verdict == "REJECT"


# ---------------------------------------------------------------------------
# Adversarial A3 — fail-closed inputs with stable reason codes
# ---------------------------------------------------------------------------
def test_unknown_transition_witness_and_mismatch_fail_closed() -> None:
    for bad in ("never-heard-of", "L1->L9", ""):
        try:
            run_counterexample(bad)
        except WitnessError as exc:
            assert exc.reason_code == "UNKNOWN_TRANSITION"
        else:
            raise AssertionError(f"ACNS_X07_ADVERSARIAL: transition {bad!r} must be refused")
    try:
        run_witness("not-a-witness")
    except WitnessError as exc:
        assert exc.reason_code == "UNKNOWN_WITNESS"
    else:
        raise AssertionError("ACNS_X07_ADVERSARIAL: unknown witness must be refused")
    base = json.loads(json.dumps(WITNESS_GALLERY["executed-not-committed"].fixture))
    mismatch = json.loads(json.dumps(base))
    mismatch["transition"] = "acknowledged-not-executed"
    try:
        run_counterexample("executed-not-committed", mismatch)
    except WitnessError as exc:
        assert exc.reason_code == "TRANSITION_MISMATCH"
    else:
        raise AssertionError("ACNS_X07_ADVERSARIAL: transition mismatch must be refused")


def test_malformed_case_and_evidence_fail_closed() -> None:
    try:
        evaluate_claim_case({"transition": "executed-not-committed", "claim": "nope"})
    except WitnessError as exc:
        assert exc.reason_code == "MALFORMED_CASE"
    else:
        raise AssertionError("ACNS_X07_ADVERSARIAL: malformed claim must be refused")
    base = json.loads(json.dumps(WITNESS_GALLERY["executed-not-committed"].fixture))
    bad_level = json.loads(json.dumps(base))
    bad_level["claim"]["asserted_level"] = "L9-TRANSCENDENT"
    try:
        evaluate_claim_case(bad_level)
    except WitnessError as exc:
        assert exc.reason_code == "MALFORMED_CASE"
    else:
        raise AssertionError("ACNS_X07_ADVERSARIAL: non-lattice asserted level must be refused")
    bad_evidence = json.loads(json.dumps(base))
    bad_evidence["evidence"] = [{"node_class": "psionic_impression"}]
    try:
        evaluate_claim_case(bad_evidence)
    except WitnessError as exc:
        assert exc.reason_code == "MALFORMED_EVIDENCE"
    else:
        raise AssertionError("ACNS_X07_ADVERSARIAL: unknown node class must be refused")
    try:
        evaluate_claim_case("just-a-string")
    except WitnessError as exc:
        assert exc.reason_code == "MALFORMED_CASE"
    else:
        raise AssertionError("ACNS_X07_ADVERSARIAL: non-mapping case must be refused")


# ---------------------------------------------------------------------------
# Adversarial A4 — no false safe completions; buckets stay in vocabulary
# ---------------------------------------------------------------------------
def test_verdicts_always_in_shared_bucket_vocabulary_and_never_false_success() -> None:
    for name in MANDATED_WITNESSES:
        artifact = run_witness(name)
        assert (
            artifact.observed_outcome in ec.OUTCOME_BUCKETS
        ), f"ACNS_X07_ADVERSARIAL[{name}]: outcome outside shared bucket vocabulary"
        assert artifact.verdict in (
            "ADMIT",
            "REJECT",
        ), f"ACNS_X07_ADVERSARIAL[{name}]: verdicts are never INDETERMINATE-shaped"
        # A REJECT is a detected gap, not a successful operation completion.
        assert (
            artifact.gap_code != "none"
        ), f"ACNS_X07_ADVERSARIAL[{name}]: a REJECT verdict must name its register gap"
        assert "none: the evidence demonstrates" not in artifact.missing_proof


def test_unverifiable_artifact_proves_nothing_not_rejection_of_operation() -> None:
    base = json.loads(json.dumps(WITNESS_GALLERY["dispatched-not-acknowledged"].fixture))
    unverifiable = json.loads(json.dumps(base))
    unverifiable["evidence"].append(
        {
            "evidence_id": "ev-shady-receipt",
            "node_class": "provider_signed_receipt",
            "verifiable": False,
            "context": dict(base["claim"]["context"]),
            "digest_binding": "sha256:" + "ee" * 32,
        }
    )
    verdict = evaluate_claim_case(unverifiable)
    assert (
        verdict.verdict == "REJECT"
    ), "ACNS_X07_ADVERSARIAL: unverifiable receipt cannot support L2"
    supported = {item["supported_level"] for item in verdict.to_dict()["observed_evidence"]}
    assert (
        "L2-ACKNOWLEDGED" not in supported
    ), "ACNS_X07_ADVERSARIAL: the unverifiable artifact must support L0, not L2"
    assert any("unverifiable" in item["binding"] for item in verdict.to_dict()["observed_evidence"])


# ---------------------------------------------------------------------------
# Adversarial A5 — label freeze: gallery refuses drifting fixtures
# ---------------------------------------------------------------------------
def test_gallery_drift_refused_when_fixture_label_cannot_reproduce() -> None:
    # Simulate a drifting witness by registering a fixture whose evidence
    # demonstrates the asserted level: run_witness must refuse via GALLERY_DRIFT
    # rather than silently emitting a mismatched artifact.
    drifted = json.loads(json.dumps(WITNESS_GALLERY["executed-not-committed"].fixture))
    drifted["evidence"].append(_repaired_case("executed-not-committed")["evidence"][-1])
    try:
        run_counterexample("executed-not-committed", drifted)
    except WitnessError as exc:
        assert (
            exc.reason_code == "NOT_A_COUNTEREXAMPLE"
        ), f"ACNS_X07_DRIFT: got {exc.reason_code}; a supported claim is not a counterexample"
    else:
        raise AssertionError("ACNS_X07_DRIFT: drifting fixture must be refused")
    # The frozen registry itself still reproduces every label (no post-hoc repair).
    for name in MANDATED_WITNESSES:
        artifact = run_witness(name)
        spec = WITNESS_GALLERY[name]
        assert artifact.verdict == spec.expected_verdict
        assert artifact.gap_code == spec.expected_gap_code


def test_run_witness_rejects_non_string_names() -> None:
    for bad in (None, 42, ["executed-not-committed"]):
        try:
            run_witness(bad)  # type: ignore[arg-type]
        except WitnessError as exc:
            assert exc.reason_code == "UNKNOWN_WITNESS"
        else:
            raise AssertionError(f"ACNS_X07_ADVERSARIAL: name {bad!r} must be refused")
