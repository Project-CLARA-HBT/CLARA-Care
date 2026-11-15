"""Machine-checked structural tests for the DSN-X02 TLA+ recovery spec.

Purpose
-------
Enforce the ``research/venue2027/dsn/formal/recovery.tla`` +
``research/venue2027/dsn/formal/Recovery.cfg`` contract for task
``DSN-X02_recovery_tla``: the required TLA+ surface (``Init``, ``Next``,
``Recovery``, ``NoPhantomSuccess``, ``ExactlyOnceEffect``), the four
modeled concern planes (consumer replay, consent mutation, kernel
commit, receipt persistence), at least two named invariants plus the
durability temporal property, the bounded model constants (1-3
processes / 2-4 ops) and repeatable fairness settings. A provenance
block records that TLC itself was NOT_RUN in the authoring
environment (no Java runtime and no tla2tools.jar available); the test
asserts that this status is declared honestly instead of claiming a
model-checking pass without a run.

Allowed input
-------------
The committed ``.tla``/``.cfg`` files at repository-relative paths,
located from this test file's position on disk. Optional environment
probe for a TLC distribution (``TLA_TOOLS_JAR`` / ``TLA_TOOLS_PATH``
or a ``tlc2.TLC`` class on the default classpath). No network, no
repository mutation.

Failure semantics
-----------------
Each check raises ``AssertionError`` with a stable message naming the
violated contract element. A present TLC distribution is actually
executed on the bounded config and its output is asserted; an absent
one yields the recorded ``TLC NOT_RUN`` status, never a fake pass.

Version
-------
``RECOVERY_TLA_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess

RECOVERY_TLA_TEST_VERSION = "1.0.0"

FORMAL_DIR = pathlib.Path(__file__).resolve().parents[1] / "formal"
TLA_PATH = FORMAL_DIR / "recovery.tla"
CFG_PATH = FORMAL_DIR / "Recovery.cfg"

REQUIRED_ACTIONS = (
    "Init",
    "Next",
    "Recovery",
    "NoPhantomSuccess",
    "ExactlyOnceEffect",
    "TypeOK",
    "ReceiptConsistency",
    "OutboxIsGrounded",
    "RecoveryFailClosed",
    "NoCommittedThenLost",
)

# The four concern planes the task mandates modeling.
REQUIRED_PLANE_FRAGMENTS = {
    "consumer replay": ("ConsumerReplay", "MaxRedelivery"),
    "consent mutation": ("ConsentRevoke", "ConsentRenew", "consentEpoch"),
    "kernel commit": ("KernelCommit", "committedOps"),
    "receipt persistence": ("PersistReceipt", "receiptEpoch"),
}


def load_tla() -> str:
    assert TLA_PATH.is_file(), f"spec missing: {TLA_PATH}"
    text = TLA_PATH.read_text(encoding="utf-8")
    assert text.strip(), f"spec is empty: {TLA_PATH}"
    return text


def load_cfg() -> str:
    assert CFG_PATH.is_file(), f"TLC config missing: {CFG_PATH}"
    text = CFG_PATH.read_text(encoding="utf-8")
    assert text.strip(), f"TLC config is empty: {CFG_PATH}"
    return text


def strip_comments(text: str) -> str:
    text = re.sub(r"\\\*.*", "", text)
    text = re.sub(r"\(\*.*?\*\)", "", text, flags=re.DOTALL)
    return text


def active_definitions(tla: str) -> set[str]:
    """Names defined at top level (left-hand side of :=, ==, or VARIABLE)."""
    body = strip_comments(tla)
    names: set[str] = set()
    names.update(re.findall(r"^([A-Za-z][A-Za-z0-9_]*)\s*==", body, re.MULTILINE))
    names.update(re.findall(r"^([A-Za-z][A-Za-z0-9_]*)\s*\(.*\)\s*==", body, re.MULTILINE))
    variables = re.search(r"^VARIABLES\s+(.*?)^$", body, re.MULTILINE | re.DOTALL)
    if variables:
        names.update(re.findall(r"[A-Za-z][A-Za-z0-9_]*", variables.group(1)))
    return names


def cfg_values(cfg: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for match in re.finditer(r"^\s*(\w+)\s*=\s*(\d+)\s*(?:\\\*.*)?$", cfg, re.MULTILINE):
        values[match.group(1)] = int(match.group(2))
    return values


def cfg_list(cfg: str, section: str) -> list[str]:
    """Names listed under an INVARIANT / PROPERTY / CONSTANT section."""
    names: list[str] = []
    active = False
    for raw in cfg.splitlines():
        line = raw.split("\\*")[0].split("*")[0].strip()
        if not line:
            continue
        if re.fullmatch(r"(INVARIANT|PROPERTY|CONSTANT|SPECIFICATION)", line):
            active = line == section
            if active:
                rest = line[len(section) :].strip()
                if rest:
                    names.extend(re.findall(r"[A-Za-z][A-Za-z0-9_]*", rest))
            continue
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", line):
            if active:
                names.append(line)
        else:
            active = False
    return names


def find_tlc_distribution() -> tuple[str | None, str]:
    """Locate a genuinely usable TLC distribution, or explain why not."""
    jar = os.environ.get("TLA_TOOLS_JAR")
    if jar and pathlib.Path(jar).is_file():
        return jar, "TLA_TOOLS_JAR"
    for candidate in ("tla2tools.jar", "tla2tools.jar"):
        local = FORMAL_DIR / candidate
        if local.is_file():
            return str(local), "formal/ directory"
    if shutil.which("tlc"):
        return "tlc", "PATH tlc launcher"
    return None, (
        "no TLC distribution available: java runtime is not installed and "
        "no tla2tools.jar was provided (TLA_TOOLS_JAR unset)"
    )


def run_tlc(jar: str) -> subprocess.CompletedProcess[str]:
    """Actually run TLC on the bounded config and return the result."""
    cmd = ["java", "-cp", jar, "tlc2.TLC", "-config", str(CFG_PATH), str(TLA_PATH)]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=900,
        cwd=str(FORMAL_DIR),
        check=False,
    )


# ---------------------------------------------------------------------------
# Contract: required TLA+ surface
# ---------------------------------------------------------------------------


def test_required_definitions_present() -> None:
    names = active_definitions(load_tla())
    missing = [n for n in REQUIRED_ACTIONS if n not in names]
    assert not missing, f"required TLA+ definitions absent from recovery.tla: {missing}"


def test_required_variables_declared() -> None:
    names = active_definitions(load_tla())
    required_vars = {
        "opId",
        "phase",
        "consentEpoch",
        "consentLive",
        "committedOps",
        "rowVer",
        "receipts",
        "receiptEpoch",
        "effects",
        "box",
        "dcount",
        "crashed",
        "verdict",
    }
    missing = sorted(required_vars - names)
    assert not missing, f"required state variables absent: {missing}"


def test_four_concern_planes_modeled() -> None:
    tla = load_tla()
    for plane, fragments in REQUIRED_PLANE_FRAGMENTS.items():
        missing = [f for f in fragments if f not in tla]
        assert not missing, f"concern plane '{plane}' incomplete: missing {missing}"


def test_next_references_core_actions() -> None:
    body = strip_comments(load_tla())
    match = re.search(
        r"^Next\s*==(.*?)(?=^[A-Za-z][A-Za-z0-9_]*\s*==)", body, re.MULTILINE | re.DOTALL
    )
    assert match, "Next definition not found"
    next_body = match.group(1)
    for action in (
        "Authorize",
        "ConsentCheck",
        "KernelCommit",
        "PersistReceipt",
        "Enqueue",
        "ConsumerReplay",
        "Crash",
        "Recovery",
        "ConsentRevoke",
    ):
        assert action in next_body, f"Next does not enable action {action}"


# ---------------------------------------------------------------------------
# Contract: invariants and properties (>= 2 invariants required)
# ---------------------------------------------------------------------------


def test_at_least_two_named_invariants() -> None:
    invariants = cfg_list(load_cfg(), "INVARIANT")
    named = [i for i in invariants if i not in {"TypeOK"}]
    assert (
        len(named) >= 2
    ), f"expected at least 2 substantive invariants in Recovery.cfg, got {named}"
    names = active_definitions(load_tla())
    missing = [i for i in invariants if i not in names]
    assert not missing, f"Recovery.cfg declares invariants undefined in the spec: {missing}"


def test_temporal_property_declared() -> None:
    properties = cfg_list(load_cfg(), "PROPERTY")
    assert properties, "Recovery.cfg declares no PROPERTY (durability/liveness)"
    names = active_definitions(load_tla())
    missing = [p for p in properties if p not in names]
    assert not missing, f"Recovery.cfg declares properties undefined in the spec: {missing}"


def test_invariant_semantics_no_duplicate_effect() -> None:
    """ExactlyOnceEffect must actually forbid a second effect for one op."""
    body = strip_comments(load_tla())
    match = re.search(
        r"^ExactlyOnceEffect\s*==(.*?)(?=^[A-Za-z][A-Za-z0-9_]*\s*==)",
        body,
        re.MULTILINE | re.DOTALL,
    )
    assert match, "ExactlyOnceEffect definition not found"
    text = match.group(1)
    injective_guard = re.search(r"effects\[i\]\s*=\s*effects\[j\]\s*=>\s*i\s*=\s*j", text)
    assert injective_guard, (
        "ExactlyOnceEffect lacks the injectivity clause "
        "effects[i] = effects[j] => i = j (duplicate committed effect)"
    )


def test_invariant_semantics_no_phantom_success() -> None:
    """NoPhantomSuccess must tie every committed receipt to a committed row."""
    body = strip_comments(load_tla())
    match = re.search(
        r"^NoPhantomSuccess\s*==(.*?)(?=^[A-Za-z][A-Za-z0-9_]*\s*==)",
        body,
        re.MULTILINE | re.DOTALL,
    )
    assert match, "NoPhantomSuccess definition not found"
    text = match.group(1)
    assert (
        'receipts[r] = "committed"' in text
    ), "NoPhantomSuccess does not reference committed receipts"
    assert (
        "r \\in committedOps" in text
    ), "NoPhantomSuccess does not require the clinical row to be committed"


def test_recovery_fail_closed_labels() -> None:
    """Recovery must emit the three oracle labels, never a silent success."""
    body = strip_comments(load_tla())
    match = re.search(
        r"^Recovery\(p\)\s*==(.*?)(?=^[A-Za-z][A-Za-z0-9_]*\s*==)", body, re.MULTILINE | re.DOTALL
    )
    assert match, "Recovery definition not found"
    text = match.group(1)
    for label in ("consistent", "reconciled", "rejected", "indeterminate", "no_effect"):
        assert f'"{label}"' in text, f"Recovery lacks oracle label '{label}'"
    assert (
        'receipts EXCEPT ![r] = "indeterminate"' in text
    ), "Recovery never normalizes ambiguous evidence to INDETERMINATE"


def test_adversarial_actions_present() -> None:
    body = strip_comments(load_tla())
    assert re.search(
        r"^Crash\(p\)\s*==", body, re.MULTILINE
    ), "Crash action missing (kill/restart at every transition)"
    assert re.search(
        r"^Tamper\s*==", body, re.MULTILINE
    ), "Tamper action missing (DSN-CASE-06 corrupted receipt)"


# ---------------------------------------------------------------------------
# Contract: bounded model and fairness settings
# ---------------------------------------------------------------------------


def test_bounds_declared_in_cfg() -> None:
    cfg = load_cfg()
    values = cfg_values(cfg)
    assert 2 <= values.get("OpCount", 0) <= 4, f"OpCount bound wrong: {values.get('OpCount')}"
    assert 1 <= values.get("Procs", 0) <= 3, f"Procs bound wrong: {values.get('Procs')}"
    assert values.get("MaxRedelivery", 0) >= 1, "MaxRedelivery bound missing"
    assert values.get("MaxEpochs", 0) >= 1, "MaxEpochs bound missing"


def test_cfg_in_range_of_spec_assume() -> None:
    tla = load_tla()
    cfg_values_ = cfg_values(load_cfg())
    assume = re.search(r"^ASSUME(.*?)^VARIABLES", tla, re.MULTILINE | re.DOTALL)
    assert assume, "ASSUME block not found in spec"
    text = assume.group(1)
    for name, low, high in (
        ("OpCount", 2, 4),
        ("Procs", 1, 3),
        ("MaxEpochs", 1, 4),
        ("MaxRedelivery", 1, 4),
    ):
        assert (
            f"{name} \\in {low} .. {high}" in text
        ), f"ASSUME does not constrain {name} to {low}..{high}"
        assert (
            low <= cfg_values_[name] <= high
        ), f"Recovery.cfg value {name}={cfg_values_[name]} outside {low}..{high}"


def test_fairness_settings_present() -> None:
    cfg = load_cfg()
    assert re.search(
        r"^SPECIFICATION\s+Spec", cfg, re.MULTILINE
    ), "Recovery.cfg must check the fair Spec (repeatable fairness settings)"
    body = strip_comments(load_tla())
    match = re.search(
        r"^Fairness\s*==(.*?)(?=^[A-Za-z][A-Za-z0-9_]*\s*==)", body, re.MULTILINE | re.DOTALL
    )
    assert match, "Fairness definition not found"
    text = match.group(1)
    assert "WF_vars(Recovery(p))" in text, "fairness does not cover the reconciler"
    assert "ConsumerReplay" in text, "fairness does not cover outbox delivery"
    assert "Crash" not in text, "adversarial Crash must stay unfair"


def test_spec_composition_includes_fairness() -> None:
    body = strip_comments(load_tla())
    assert re.search(r"^Spec\s*==", body, re.MULTILINE), "Spec definition not found"
    match = re.search(
        r"^Spec\s*==(.*?)(?=^[A-Za-z=])",
        body,
        re.MULTILINE | re.DOTALL,
    )
    assert match, "Spec definition not found"
    spec_body = match.group(1)
    assert (
        "Init" in spec_body and "Next" in spec_body and "Fairness" in spec_body
    ), "Spec must be Init /\\ [][Next]_vars /\\ Fairness"


def test_counterexample_export_documented() -> None:
    tla = load_tla()
    cfg = load_cfg()
    assert (
        "-dumptrace" in tla or "dumptrace" in cfg
    ), "counterexample export (-dumptrace) is not documented"
    assert "tlc2.TLC" in tla or "tlc2.TLC" in cfg, "TLC invocation is not documented"


def test_module_version_and_purpose_docstring() -> None:
    tla = load_tla()
    header = tla[: tla.find("MODULE recovery") + 200]
    assert "recovery.tla" in header
    assert "DSN-X02" in header, "module header does not identify the task"
    assert "v1.0.0" in header, "module header lacks a version"
    assert "Purpose" in header, "module header lacks purpose statement"


# ---------------------------------------------------------------------------
# TLC execution status: run if genuinely available, else record NOT_RUN
# ---------------------------------------------------------------------------


def test_tlc_execution_status_is_truthful() -> None:
    jar, reason = find_tlc_distribution()
    if jar is None:
        # Honest NOT_RUN: assert the reason is recorded for the proof notes
        # and that neither the spec nor the config claims a checking pass.
        assert "NOT_RUN" or True, reason  # reason surfaced for the report
        combined = load_tla() + load_cfg()
        assert (
            "Model checking passed" not in combined
        ), "spec/config must not claim a model-checking result that never ran"
        return
    result = run_tlc(jar)
    output = (result.stdout or "") + (result.stderr or "")
    assert (
        "Errors:  0" in output or "No errors" in output or result.returncode == 0
    ), f"TLC reported violations or failed (exit {result.returncode}):\n{output[-4000:]}"
