"""Tests for the bounded exhaustive enumerator."""

from __future__ import annotations

import unittest

from evaluation.formal_governance.explore import TOOL_VERSION, explore
from evaluation.formal_governance.model import initial_state


class ExploreReportTests(unittest.TestCase):
    def test_report_shape_and_zero_violations(self) -> None:
        report = explore(max_depth=4)
        self.assertEqual(report["violation_count"], 0)
        self.assertEqual(report["violations"], [])
        self.assertGreater(report["states"], 0)
        self.assertGreater(report["transitions_explored"], 0)
        self.assertGreaterEqual(report["admitted"], report["admitted_commits"])
        self.assertGreaterEqual(report["states"], report["distinct_canonical_coordinates"])
        self.assertLessEqual(report["max_depth_reached"], report["max_depth"])
        self.assertEqual(report["tool_version"], TOOL_VERSION)
        self.assertEqual(len(report["source_sha"]), 64)
        self.assertGreater(report["runtime_seconds"], 0)

    def test_i11_clean_commit_reachable_in_report(self) -> None:
        report = explore(max_depth=4)
        self.assertTrue(report["i11_clean_commit_reachable"])

    def test_exploration_reaches_admitted_commits(self) -> None:
        report = explore(max_depth=4)
        self.assertGreater(report["admitted_commits"], 0)

    def test_runtime_stays_bounded(self) -> None:
        report = explore(max_depth=5)
        self.assertLess(report["runtime_seconds"], 30)


class ExploreDeterminismTests(unittest.TestCase):
    def test_two_runs_identical(self) -> None:
        first = explore(max_depth=4)
        second = explore(max_depth=4)
        self.assertEqual(first["states"], second["states"])
        self.assertEqual(first["transitions_explored"], second["transitions_explored"])
        self.assertEqual(first["admitted_commits"], second["admitted_commits"])
        self.assertEqual(first["violations"], second["violations"])
        self.assertEqual(first["source_sha"], second["source_sha"])


class ExploreCoverageTests(unittest.TestCase):
    def test_deeper_exploration_is_superset(self) -> None:
        shallow = explore(max_depth=3)
        deep = explore(max_depth=4)
        self.assertGreaterEqual(deep["states"], shallow["states"])
        self.assertGreaterEqual(deep["transitions_explored"], shallow["transitions_explored"])

    def test_each_required_transition_is_explored(self) -> None:
        # Every defined transition name must be attempted at least once.
        report = explore(max_depth=4)
        expected_names = {
            "issue_disclosure",
            "create_proposal",
            "advance_state",
            "revoke_consent",
            "change_role",
            "change_purpose",
            "advance_policy",
            "expire_snapshot",
            "corrupt_digest",
            "replay_proposal",
            "commit",
            "retry",
            "rollback",
        }
        counts = report["transition_counts"]
        self.assertTrue(set(counts) == expected_names)


class CounterexampleRetentionTests(unittest.TestCase):
    def test_hook_violation_reported_with_minimal_path(self) -> None:
        fired = False

        def check(cur, name, params, outcome):
            nonlocal fired
            if name == "advance_state" and cur == initial_state():
                fired = True
                return ["I_TEST_INJECTED"]
            return []

        report = explore(max_depth=3, transition_check_extra=check)
        self.assertTrue(fired)
        self.assertEqual(report["violation_count"], 1)
        invariant, path, source, transition, _reason = report["violations"][0]
        self.assertEqual(invariant, "I_TEST_INJECTED")
        self.assertEqual(path, ("advance_state",))
        self.assertEqual(transition, "advance_state")
        self.assertEqual(source, initial_state())

    def test_deeper_does_not_duplicate_minimal_counterexample(self) -> None:
        def check(cur, name, params, outcome):
            if name == "advance_state":
                return ["I_TEST_INJECTED"]
            return []

        report = explore(max_depth=4, transition_check_extra=check)
        self.assertEqual(report["violation_count"], 1)


if __name__ == "__main__":
    unittest.main()
