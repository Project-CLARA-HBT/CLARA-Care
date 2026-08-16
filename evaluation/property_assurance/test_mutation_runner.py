from __future__ import annotations

import subprocess
from pathlib import Path

from evaluation.property_assurance.mutation_overlay import MutantOverlay
from evaluation.property_assurance.mutation_runner import (
    absolute_pytest_targets,
    execute_mutant,
    load_catalog_mutant,
    repository_revision,
    suite_targets,
    target_file_hashes,
)


def _repository(root: Path) -> None:
    source = root / "services/api/src/clara_api"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("", encoding="utf-8")
    (source / "gate.py").write_text("if policy_check:\n    reject()\n", encoding="utf-8")
    (root / "evaluation").mkdir()
    tests = root / "services/api/tests"
    tests.mkdir(parents=True)
    (tests / "test_gate.py").write_text("def test_gate(): pass\n", encoding="utf-8")


def test_timeout_is_not_counted_as_a_killed_mutant(monkeypatch, tmp_path: Path) -> None:
    _repository(tmp_path)

    def timeout(*args, **kwargs):
        if args[0][0] == "git":
            return subprocess.CompletedProcess(args=args[0], returncode=1, stdout="")
        if "-c" in args[0]:
            imported = Path(kwargs["cwd"]) / "services/api/src/clara_api/__init__.py"
            return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=str(imported))
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"], output="partial")

    monkeypatch.setattr("evaluation.property_assurance.mutation_runner.subprocess.run", timeout)
    result = execute_mutant(
        repository_root=tmp_path,
        mutant=MutantOverlay(
            "M02-A", "services/api/src/clara_api/gate.py", "policy_check", "False"
        ),
        pytest_targets=["services/api/tests/test_gate.py"],
    )

    assert result["classification"] == "INFRASTRUCTURE_ERROR_NOT_KILLED"
    assert result["returncode"] is None
    assert result["error"] == "govmut_pytest_timeout"


def test_catalog_loader_rejects_missing_or_ambiguous_mutant(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.json"
    catalog.write_text('{"candidates": [{"id": "M", "source_path": "a", "anchor": "b", "replacement": "c"}]}')
    assert load_catalog_mutant(catalog_path=catalog, mutant_id="M").source_path == "a"
    try:
        load_catalog_mutant(catalog_path=catalog, mutant_id="unknown")
    except ValueError as exc:
        assert str(exc) == "govmut_catalog_mutant_not_unique"
    else:
        raise AssertionError("missing mutant must fail closed")


def test_target_hashes_require_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "test_gate.py"
    target.write_text("pass\n", encoding="utf-8")
    hashes = target_file_hashes(repository_root=tmp_path, pytest_targets=["test_gate.py"])
    assert hashes["test_gate.py"]
    try:
        target_file_hashes(repository_root=tmp_path, pytest_targets=["missing.py"])
    except ValueError as exc:
        assert str(exc) == "govmut_pytest_target_must_be_existing_file"
    else:
        raise AssertionError("missing target must fail closed")


def test_absolute_targets_preserve_node_selector(tmp_path: Path) -> None:
    assert absolute_pytest_targets(
        repository_root=tmp_path, pytest_targets=["tests/test_gate.py::test_gate"]
    ) == [f"{tmp_path}/tests/test_gate.py::test_gate"]


def test_revision_is_explicitly_unavailable_for_non_repository_fixture(tmp_path: Path) -> None:
    assert repository_revision(tmp_path) == "UNAVAILABLE"


def test_suite_targets_rejects_unknown_method_and_uses_the_checked_matrix(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.json"
    matrix.write_text(
        """{
          "status": "development_only_not_frozen",
          "suites": {
            "M0_regression": ["m0.py"],
            "M1_stateless_property": ["m1.py"],
            "M2_state_machine": ["m2.py"],
            "M3_combined": ["m0.py", "m1.py", "m2.py"]
          }
        }""",
        encoding="utf-8",
    )
    assert suite_targets(matrix_path=matrix, method="M1_stateless_property") == ["m1.py"]
    try:
        suite_targets(matrix_path=matrix, method="M4_api")
    except ValueError as exc:
        assert str(exc) == "govmut_suite_method_invalid"
    else:
        raise AssertionError("unknown method must fail closed")


def test_runner_uses_staged_cwd_and_absolute_test_target(monkeypatch, tmp_path: Path) -> None:
    _repository(tmp_path)
    observed: dict[str, object] = {}

    def completed(args, **kwargs):
        if args[0] == "git":
            return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="")
        observed.update({"args": args, "cwd": kwargs["cwd"], "env": kwargs["env"]})
        if "-c" in args:
            imported = Path(kwargs["cwd"]) / "services/api/src/clara_api/__init__.py"
            return subprocess.CompletedProcess(args=args, returncode=0, stdout=str(imported), stderr="")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("evaluation.property_assurance.mutation_runner.subprocess.run", completed)
    result = execute_mutant(
        repository_root=tmp_path,
        mutant=MutantOverlay(
            "M02-A", "services/api/src/clara_api/gate.py", "policy_check", "False"
        ),
        pytest_targets=["services/api/tests/test_gate.py"],
    )

    assert result["classification"] == "SURVIVED"
    assert observed["cwd"] != tmp_path
    assert observed["args"][-1] == str(
        Path(observed["cwd"]) / "services/api/tests/test_gate.py"
    )
    assert str(observed["env"]["PYTHONPATH"]).startswith(
        str(Path(observed["cwd"]) / "services/api/src")
    )
    assert str(tmp_path) not in str(observed["env"]["PYTHONPATH"])


def test_runner_records_and_forwards_hypothesis_seed(monkeypatch, tmp_path: Path) -> None:
    _repository(tmp_path)
    commands: list[list[str]] = []

    def completed(args, **kwargs):
        if args[0] == "git":
            return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="")
        commands.append(args)
        if "-c" in args:
            imported = Path(kwargs["cwd"]) / "services/api/src/clara_api/__init__.py"
            return subprocess.CompletedProcess(args=args, returncode=0, stdout=str(imported), stderr="")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("evaluation.property_assurance.mutation_runner.subprocess.run", completed)
    result = execute_mutant(
        repository_root=tmp_path,
        mutant=MutantOverlay("M02-A", "services/api/src/clara_api/gate.py", "policy_check", "False"),
        pytest_targets=["services/api/tests/test_gate.py"],
        hypothesis_seed=20260817,
    )

    assert result["hypothesis_seed"] == 20260817
    assert ["--hypothesis-seed", "20260817"] == commands[-1][4:6]


def test_runner_rejects_workspace_import_during_probe(monkeypatch, tmp_path: Path) -> None:
    _repository(tmp_path)

    def workspace_import(args, **kwargs):
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout=str(tmp_path / "services/api/src/clara_api/__init__.py")
        )

    monkeypatch.setattr("evaluation.property_assurance.mutation_runner.subprocess.run", workspace_import)
    try:
        execute_mutant(
            repository_root=tmp_path,
            mutant=MutantOverlay(
                "M02-A", "services/api/src/clara_api/gate.py", "policy_check", "False"
            ),
            pytest_targets=["services/api/tests/test_gate.py"],
        )
    except RuntimeError as exc:
        assert str(exc) == "govmut_staged_import_probe_failed"
    else:
        raise AssertionError("workspace import must fail closed")
