"""Machine-checked preregistration test for the DSN 2027 RQ/estimand registry.

Purpose
-------
Enforce the frozen preregistration structure of
``research/venue2027/dsn/rq_and_estimands.yaml`` (task ``DSN-rq_registry``):
exactly three research questions, each carrying every required estimand
field (question text, independent unit, population, estimand, paired
contrast, primary and secondary metrics, null hypothesis, alternative,
minimum useful difference, confounders, power/analysis method) plus a
non-empty ``falsification_condition`` and a ``primary_endpoint`` that
differs across RQs, with no invented numeric results anywhere in the file.
The registry is written as a JSON-compatible YAML subset and parsed by the
tiny stdlib parser in this module (``parse_yaml_subset``); ``read_rqs()``
realizes the task's declared ``read_rqs()->RQPlan`` signature without pyyaml.

Allowed input
-------------
The registry file at repository-relative path
``research/venue2027/dsn/rq_and_estimands.yaml``, plus small inline
parser vectors defined in this module. No network, no database, no
filesystem writes, no third-party dependencies.

Failure semantics
-----------------
Each check raises ``AssertionError`` with a stable message naming the
missing or drifted structural element; parser violations raise
``YamlSubsetError``. Tampering vectors operate on deep copies only; the
preregistered file itself is only read here.

Version
-------
``RQ_REGISTRY_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import copy
import pathlib
import re
import unittest

RQ_REGISTRY_TEST_VERSION = "1.0.0"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
REGISTRY_PATH = REPO_ROOT / "research" / "venue2027" / "dsn" / "rq_and_estimands.yaml"

REQUIRED_RQ_FIELDS: tuple[str, ...] = (
    "id",
    "question_text",
    "independent_unit",
    "population",
    "estimand",
    "paired_contrast",
    "primary_metric",
    "secondary_metrics",
    "null_hypothesis",
    "alternative",
    "minimum_useful_difference",
    "confounders",
    "power_analysis_method",
    "analysis_method",
    "primary_endpoint",
    "falsification_condition",
    "plan_status",
)

BLUEPRINT_RQ_TEXT: dict[str, str] = {
    "RQ1": (
        "Across crash cut points, are there executions where the clinical state, "
        "decision receipt, and outbox state disagree after bounded recovery?"
    ),
    "RQ2": (
        "Under at-least-once replay and concurrent consent revocation, does recovery "
        "preserve idempotence, causal order, and correct INDETERMINATE labels?"
    ),
    "RQ3": (
        "What is the added durable-write, p99 latency and recovery-time cost compared "
        "with transactional outbox and durable workflow baselines?"
    ),
}

PRIMARY_ENDPOINT_ANCHORS: dict[str, str] = {
    "RQ1": "inconsistency",
    "RQ2": "replay",
    "RQ3": "cost",
}

FALSIFICATION_BASELINE_ANCHORS: dict[str, str] = {"RQ1": "B1", "RQ2": "B2"}

REQUIRED_BASELINE_ARMS: tuple[str, ...] = ("B0", "B1", "B2", "B3")

RESULT_SHAPES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bp\s*=\s*0?\.\d+", re.IGNORECASE),
    re.compile(r"\bp\s*[<>]\s*0?\.\d+", re.IGNORECASE),
    re.compile(r"\bp9[05]\s*=\s*\d+", re.IGNORECASE),
    re.compile(
        r"\b(reduced?|improved?|lowered?|increased?)\s+by\s+\d+(\.\d+)?\s*%",
        re.IGNORECASE,
    ),
    re.compile(r"\b\d+(\.\d+)?\s*(ms|milliseconds)\b", re.IGNORECASE),
    re.compile(r"\b(results?|measurements?)\s*:\s*\d", re.IGNORECASE),
    re.compile(r"\bobserved\s+(rate|count|value|fraction)\D*\d", re.IGNORECASE),
    re.compile(r"\b\d+(\.\d+)?\s*(orphan|phantom|duplicate)\b", re.IGNORECASE),
    re.compile(r"\bspeedup\b", re.IGNORECASE),
)


class YamlSubsetError(ValueError):
    """Raised for YAML constructs outside the supported JSON-compatible subset."""


_KV_LINE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*:(\s|$)")


def _strip_comment(line: str) -> str:
    chars: list[str] = []
    in_single = in_double = False
    for ch in line:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double and (not chars or chars[-1] in " \t"):
            break
        chars.append(ch)
    return "".join(chars).rstrip()


def _scalar(token: str) -> str | int | float | bool | None:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
        return token[1:-1]
    if token in ("", "null", "~"):
        return None
    if re.fullmatch(r"[+-]?\d+", token):
        return int(token)
    if re.fullmatch(r"[+-]?\d+\.\d+", token):
        return float(token)
    if token == "true":
        return True
    if token == "false":
        return False
    return token


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


class _SubsetParser:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self._pos = 0

    def parse_document(self) -> dict[str, object]:
        root = self.parse_block(0)
        if self._pos != len(self._lines):
            raise YamlSubsetError(f"trailing unparsed content at line {self._pos + 1}")
        if not isinstance(root, dict):
            raise YamlSubsetError("document root must be a mapping")
        return root

    def parse_block(self, indent: int) -> object:
        line = self._lines[self._pos]
        current = _indent_of(line)
        if current != indent:
            raise YamlSubsetError(
                f"line {self._pos + 1}: expected indent {indent}, found {current}"
            )
        if line.lstrip().startswith("- "):
            return self.parse_list(indent)
        return self.parse_map(indent)

    def parse_map(self, indent: int) -> dict[str, object]:
        result: dict[str, object] = {}
        while self._pos < len(self._lines):
            line = self._lines[self._pos]
            current = _indent_of(line)
            if current < indent:
                break
            if current > indent:
                raise YamlSubsetError(f"line {self._pos + 1}: unexpected indent {current}")
            stripped = line.strip()
            if stripped.startswith("- "):
                break
            key, sep, rest = stripped.partition(":")
            if not sep or not key.strip():
                raise YamlSubsetError(f"line {self._pos + 1}: not a mapping line: {line!r}")
            key = key.strip()
            rest = rest.strip()
            self._pos += 1
            if rest:
                result[key] = _scalar(rest)
            else:
                result[key] = self._parse_child_block(indent)
        return result

    def parse_list(self, indent: int) -> list[object]:
        items: list[object] = []
        while self._pos < len(self._lines):
            line = self._lines[self._pos]
            current = _indent_of(line)
            stripped = line.strip()
            if current != indent or not stripped.startswith("- "):
                break
            content = stripped[2:].strip()
            self._pos += 1
            if not content:
                raise YamlSubsetError(f"line {self._pos}: empty list item")
            if _KV_LINE.match(content):
                self._lines[self._pos - 1] = " " * (indent + 2) + content
                self._pos -= 1
                items.append(self.parse_map(indent + 2))
            else:
                items.append(_scalar(content))
        return items

    def _parse_child_block(self, parent_indent: int) -> object:
        if self._pos >= len(self._lines):
            return None
        child_indent = _indent_of(self._lines[self._pos])
        if child_indent <= parent_indent:
            return None
        return self.parse_block(child_indent)


def parse_yaml_subset(text: str) -> dict[str, object]:
    lines: list[str] = []
    for raw in text.splitlines():
        cleaned = _strip_comment(raw)
        if cleaned.strip():
            lines.append(cleaned)
    if not lines:
        raise YamlSubsetError("registry document is empty")
    return _SubsetParser(lines).parse_document()


def load_registry() -> dict[str, object]:
    assert REGISTRY_PATH.is_file(), f"registry missing: {REGISTRY_PATH}"
    return parse_yaml_subset(REGISTRY_PATH.read_text(encoding="utf-8"))


def read_rqs() -> list[dict[str, object]]:
    registry = load_registry()
    rqs = registry.get("research_questions")
    if not isinstance(rqs, list) or len(rqs) != 3:
        raise ValueError("registry must declare exactly 3 research_questions")
    return [rq for rq in rqs if isinstance(rq, dict)]


def _require_nonempty(rq_id: object, field: str, value: object) -> None:
    assert value is not None, f"{rq_id}: missing field {field}"
    if isinstance(value, str):
        assert value.strip(), f"{rq_id}: empty field {field}"
    elif isinstance(value, list):
        assert value, f"{rq_id}: empty list field {field}"
        for element in value:
            assert str(element).strip(), f"{rq_id}: empty element in list field {field}"


def assert_valid_registry(registry: dict[str, object]) -> None:
    status = registry.get("status")
    assert status == "PREREGISTERED_DESIGN_NO_RESULTS", f"unexpected status: {status!r}"
    rqs = registry.get("research_questions")
    assert isinstance(rqs, list), "research_questions must be a list"
    assert len(rqs) == 3, f"expected exactly 3 RQs, found {len(rqs)}"
    ids: list[str] = []
    endpoints: list[str] = []
    for rq in rqs:
        assert isinstance(rq, dict), "each RQ must be a mapping"
        rq_id = rq.get("id", "?")
        for field in REQUIRED_RQ_FIELDS:
            _require_nonempty(rq_id, field, rq.get(field))
        falsification = str(rq.get("falsification_condition", "")).lower()
        assert (
            "discard" in falsification or "withdrawn" in falsification
        ), f"{rq_id}: falsification_condition must name the claim to discard"
        assert (
            rq.get("plan_status") == "PLANNED_PREREGISTERED"
        ), f"{rq_id}: plan_status must stay PLANNED_PREREGISTERED"
        ids.append(str(rq.get("id")))
        endpoints.append(str(rq.get("primary_endpoint")))
    assert ids == ["RQ1", "RQ2", "RQ3"], f"unexpected RQ ids: {ids}"
    assert len(set(endpoints)) == 3, f"primary endpoints must be pairwise distinct: {endpoints}"
    arms = registry.get("arms")
    assert isinstance(arms, list) and arms, "arms must be a non-empty list"
    arm_ids = [str(arm.get("id")) for arm in arms if isinstance(arm, dict)]
    assert arm_ids == list(REQUIRED_BASELINE_ARMS), f"unexpected arms: {arm_ids}"
    budget = registry.get("confidence_budget")
    assert isinstance(budget, dict), "confidence_budget must be a mapping"
    assert budget.get("planned_comparison_count") == 3, "planned_comparison_count must be 3"
    global_rule = str(registry.get("global_falsification_rule", "")).strip()
    nonreuse = str(registry.get("evidence_nonreuse_declaration", "")).strip()
    assert global_rule, "global_falsification_rule missing"
    assert nonreuse, "evidence_nonreuse_declaration missing"


def assert_no_result_numbers(text: str) -> None:
    for pattern in RESULT_SHAPES:
        match = pattern.search(text)
        assert match is None, f"result-shaped number forbidden in preregistration: {match!r}"


class TestRqRegistryPreregistration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        assert REGISTRY_PATH.is_file(), f"registry missing: {REGISTRY_PATH}"
        cls.raw_text = REGISTRY_PATH.read_text(encoding="utf-8")
        cls.registry = parse_yaml_subset(cls.raw_text)

    def test_exactly_three_rqs_with_all_required_fields(self) -> None:
        assert_valid_registry(self.registry)

    def test_question_text_matches_blueprint_verbatim(self) -> None:
        for rq in read_rqs():
            rq_id = str(rq.get("id"))
            self.assertEqual(rq.get("question_text"), BLUEPRINT_RQ_TEXT[rq_id], rq_id)

    def test_primary_endpoints_differ_across_rqs(self) -> None:
        rqs = read_rqs()
        endpoints = [str(rq.get("primary_endpoint")) for rq in rqs]
        self.assertEqual(len(set(endpoints)), 3, "primary endpoints must be pairwise distinct")
        for rq in rqs:
            rq_id = str(rq.get("id"))
            anchor = PRIMARY_ENDPOINT_ANCHORS[rq_id]
            self.assertIn(anchor, str(rq.get("primary_endpoint")).lower(), rq_id)

    def test_falsification_conditions_nonempty_and_actionable(self) -> None:
        for rq in read_rqs():
            rq_id = str(rq.get("id"))
            condition = str(rq.get("falsification_condition", ""))
            self.assertTrue(condition.strip(), f"{rq_id}: empty falsification_condition")
            self.assertIn("discard", condition.lower(), rq_id)
            anchor = FALSIFICATION_BASELINE_ANCHORS.get(rq_id)
            if anchor is not None:
                self.assertIn(anchor, condition, f"{rq_id}: falsification must name {anchor}")

    def test_independent_unit_is_history_or_repetition_never_event(self) -> None:
        units = {str(rq.get("id")): str(rq.get("independent_unit")) for rq in read_rqs()}
        self.assertIn("history", units["RQ1"].lower(), "RQ1 unit must be a history")
        self.assertIn("history", units["RQ2"].lower(), "RQ2 unit must be a history")
        self.assertIn("repetition", units["RQ3"].lower(), "RQ3 unit must be a repetition")

    def test_clustered_analysis_rejects_pooled_pseudo_replication(self) -> None:
        rqs = read_rqs()
        for rq in rqs:
            method = str(rq.get("analysis_method", "")).lower()
            self.assertIn("cluster", method, f"{rq.get('id')}: analysis must be clustered")
        rq1_method = str(rqs[0].get("analysis_method", "")).lower()
        self.assertIn("never treated as independent", rq1_method)
        rq3_method = str(rqs[2].get("analysis_method", "")).lower()
        self.assertIn("never individual operations", rq3_method)

    def test_power_method_is_pilot_based_not_p_value_based(self) -> None:
        for rq in read_rqs():
            rq_id = str(rq.get("id"))
            power = str(rq.get("power_analysis_method", "")).lower()
            self.assertIn("pilot", power, f"{rq_id}: power must derive from pilot variance")
            self.assertIn("chosen from target p-values", power, rq_id)

    def test_no_invented_numeric_results_anywhere_in_file(self) -> None:
        assert_no_result_numbers(self.raw_text)

    def test_registry_declares_design_artifact_status(self) -> None:
        self.assertEqual(self.registry.get("status"), "PREREGISTERED_DESIGN_NO_RESULTS")
        for rq in read_rqs():
            self.assertEqual(rq.get("plan_status"), "PLANNED_PREREGISTERED")

    def test_paper_title_matches_blueprint(self) -> None:
        self.assertEqual(
            self.registry.get("paper_title"),
            "Recoverable Safety Journals for Crash-Consistent AI-Mediated Health-State Mutations",
        )

    def test_baseline_arms_and_global_falsification_rule(self) -> None:
        arms = self.registry.get("arms")
        assert isinstance(arms, list)
        arm_ids = [str(arm.get("id")) for arm in arms if isinstance(arm, dict)]
        self.assertEqual(arm_ids, list(REQUIRED_BASELINE_ARMS))
        rule = str(self.registry.get("global_falsification_rule", "")).lower()
        self.assertIn("outbox", rule)
        self.assertIn("discard", rule)

    def test_frozen_archive_nonreuse_declared(self) -> None:
        declaration = str(self.registry.get("evidence_nonreuse_declaration", "")).lower()
        self.assertIn("e15", declaration)
        self.assertIn("govred", declaration)

    def test_registry_file_uses_no_tab_indentation(self) -> None:
        self.assertNotIn("\t", self.raw_text)


class TestYamlSubsetParser(unittest.TestCase):
    def test_parses_nested_maps_and_lists(self) -> None:
        doc = parse_yaml_subset(
            'top:\n  - id: "A"\n    tags:\n      - "x"\n      - "y"\nscalar: 3\n'
        )
        self.assertEqual(doc, {"top": [{"id": "A", "tags": ["x", "y"]}], "scalar": 3})

    def test_preserves_quoted_scalars_containing_colons(self) -> None:
        doc = parse_yaml_subset("key: \"a: b\"\nother: 'c'\nnum: 0.05\nflag: false\n")
        self.assertEqual(doc, {"key": "a: b", "other": "c", "num": 0.05, "flag": False})

    def test_rejects_inconsistent_indentation(self) -> None:
        with self.assertRaises(YamlSubsetError):
            parse_yaml_subset("outer:\n    a: 1\n  b: 2\n")

    def test_rejects_tab_indentation(self) -> None:
        with self.assertRaises(YamlSubsetError):
            parse_yaml_subset("outer:\n\t- id: 1\n")

    def test_rejects_empty_document(self) -> None:
        with self.assertRaises(YamlSubsetError):
            parse_yaml_subset("# only a comment\n")


class TestTamperDetection(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry()

    def _mutated(self, mutator) -> dict[str, object]:
        doc = copy.deepcopy(self.registry)
        mutator(doc)
        return doc

    def test_removing_a_required_field_fails_validation(self) -> None:
        def mutate(doc: dict[str, object]) -> None:
            rqs = doc["research_questions"]
            assert isinstance(rqs, list) and isinstance(rqs[0], dict)
            del rqs[0]["estimand"]

        with self.assertRaises(AssertionError):
            assert_valid_registry(self._mutated(mutate))

    def test_empty_falsification_condition_fails(self) -> None:
        def mutate(doc: dict[str, object]) -> None:
            rqs = doc["research_questions"]
            assert isinstance(rqs, list) and isinstance(rqs[1], dict)
            rqs[1]["falsification_condition"] = "   "

        with self.assertRaises(AssertionError):
            assert_valid_registry(self._mutated(mutate))

    def test_shared_primary_endpoint_fails(self) -> None:
        def mutate(doc: dict[str, object]) -> None:
            rqs = doc["research_questions"]
            assert isinstance(rqs, list) and isinstance(rqs[2], dict) and isinstance(rqs[0], dict)
            rqs[2]["primary_endpoint"] = rqs[0]["primary_endpoint"]

        with self.assertRaises(AssertionError):
            assert_valid_registry(self._mutated(mutate))

    def test_wrong_rq_count_fails(self) -> None:
        def mutate(doc: dict[str, object]) -> None:
            rqs = doc["research_questions"]
            assert isinstance(rqs, list)
            doc["research_questions"] = rqs[:2]

        with self.assertRaises(AssertionError):
            assert_valid_registry(self._mutated(mutate))

    def test_observed_result_status_fails(self) -> None:
        def mutate(doc: dict[str, object]) -> None:
            doc["status"] = "RESULTS_OBSERVED"

        with self.assertRaises(AssertionError):
            assert_valid_registry(self._mutated(mutate))

    def test_missing_baseline_arm_fails(self) -> None:
        def mutate(doc: dict[str, object]) -> None:
            arms = doc["arms"]
            assert isinstance(arms, list)
            arms[:] = [arm for arm in arms if isinstance(arm, dict) and arm.get("id") != "B1"]

        with self.assertRaises(AssertionError):
            assert_valid_registry(self._mutated(mutate))

    def test_result_shaped_text_is_detected(self) -> None:
        for poisoned in (
            "measured p = 0.03 in favor of B3",
            "p99 = 412ms latency observed",
            "improved by 23% over B1",
            "reduced by 12% of histories",
            "3 orphan writes per history observed",
        ):
            with self.assertRaises(AssertionError, msg=poisoned):
                assert_no_result_numbers(poisoned)

    def test_design_parameter_text_passes(self) -> None:
        assert_no_result_numbers(
            "48 crash windows x 4 orderings x 3 schedules x 5 seeds; "
            "margin frozen at 0.01 per history; alpha = 0.05 one-sided; "
            "power computed post-pilot; upper bound formula 1 - 0.05**(1/N)"
        )


if __name__ == "__main__":
    unittest.main()
