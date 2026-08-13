"""Fail-closed contract around an upstream Microsoft GraphRAG execution.

The adapter owns only the common-cohort serialization and evidence ledger.  It
never substitutes a project-local retrieval algorithm for the upstream system.
The corresponding benchmark condition can be called an official reproduction
only when this module verifies a pinned upstream checkout and artifacts emitted
by its ``graphrag index`` and ``graphrag query`` commands.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

UPSTREAM_REPOSITORY = "https://github.com/microsoft/graphrag.git"
UPSTREAM_RELEASE = "v3.1.0"
UPSTREAM_COMMIT = "7fc6607edda3d387d23e52ededbf8a75b6730f97"
UPSTREAM_LICENSE = "MIT"
SCHEMA_VERSION = "glhs-bench-official-graphrag-contract.v1"
GLOBAL_ROUTER_CONCURRENCY = 5


class GraphRAGContractError(RuntimeError):
    """Raised when a claimed upstream GraphRAG execution lacks provenance."""


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


@dataclass(frozen=True)
class GraphRAGExecutionContract:
    """Frozen properties required for a faithful, fair external comparator."""

    upstream_repository: str = UPSTREAM_REPOSITORY
    upstream_release: str = UPSTREAM_RELEASE
    upstream_commit: str = UPSTREAM_COMMIT
    upstream_license: str = UPSTREAM_LICENSE
    input_serialization: str = "visible-evidence-jsonl.v1"
    index_command: str = "python -m graphrag index --root <run_root>"
    query_command: str = "python -m graphrag query --root <run_root>"
    equalized_solver: str = "frozen_glhs_solver_prompt_and_schema.v1"
    prohibited: tuple[str, ...] = (
        "gold_labels",
        "future_events",
        "case_specific_prompt_tuning",
        "project_local_retrieval_substitution",
        "unlogged_model_or_embedding_calls",
    )

    def canonical(self) -> dict[str, Any]:
        return asdict(self)

    def sha256(self) -> str:
        return _sha256_bytes(_canonical_json(self.canonical()))


def build_settings(
    *,
    completion_model: str,
    embedding_model: str,
    api_base_env: str = "${GRAPHRAG_API_BASE}",
    api_key_env: str = "${GRAPHRAG_API_KEY}",
) -> dict[str, Any]:
    """Return the minimal pinned upstream settings, without embedding secrets.

    Microsoft GraphRAG v3.1.0 uses LiteLLM-compatible model configuration.  A
    real execution must prove both the completion and embedding endpoint/model
    were available before indexing; unsupported router embeddings are a hard
    asset gate, not a reason to silently replace GraphRAG with local RAG.
    """

    if not completion_model or not embedding_model:
        raise GraphRAGContractError("completion_and_embedding_models_required")
    return {
        "completion_models": {
            "default_completion_model": {
                "model_provider": "openai",
                "model": completion_model,
                "auth_method": "api_key",
                "api_base": api_base_env,
                "api_key": api_key_env,
                "retry": {"type": "exponential_backoff"},
            }
        },
        "embedding_models": {
            "default_embedding_model": {
                "model_provider": "openai",
                "model": embedding_model,
                "auth_method": "api_key",
                "api_base": api_base_env,
                "api_key": api_key_env,
                "retry": {"type": "exponential_backoff"},
            }
        },
        "input": {"type": "jsonl"},
        # This is the same global cap as the GLHS-Bench solver. The external
        # indexer must run in its own frozen window, never alongside a solver
        # run, so its own upstream worker pool cannot bypass the router cap.
        "concurrent_requests": GLOBAL_ROUTER_CONCURRENCY,
        "chunking": {"type": "tokens", "size": 1200, "overlap": 100},
        "input_storage": {"type": "file", "base_dir": "input"},
        "output_storage": {"type": "file", "base_dir": "output"},
        "reporting": {"type": "file", "base_dir": "reports"},
        "cache": {"type": "none"},
        "vector_store": {"type": "lancedb", "db_uri": "output/lancedb"},
        "embed_text": {"embedding_model_id": "default_embedding_model"},
        "extract_graph": {
            "completion_model_id": "default_completion_model",
            "max_gleanings": 0,
        },
        "summarize_descriptions": {"completion_model_id": "default_completion_model"},
        "community_reports": {"completion_model_id": "default_completion_model"},
        "local_search": {
            "completion_model_id": "default_completion_model",
            "embedding_model_id": "default_embedding_model",
        },
    }


def _run_upstream_command(command: list[str], *, environment: dict[str, str] | None = None) -> None:
    """Run an upstream CLI command without retaining provider output or secrets."""

    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
    except OSError as exc:
        raise GraphRAGContractError("upstream_graphrag_cli_unavailable") from exc
    if completed.returncode != 0:
        raise GraphRAGContractError("upstream_graphrag_cli_failed")


def prepare_upstream_run_root(
    run_root: Path,
    *,
    events: list[dict[str, Any]],
    completion_model: str,
    embedding_model: str,
    upstream_checkout: Path,
    graphrag_executable: str = "graphrag",
) -> dict[str, Any]:
    """Initialize an official GraphRAG run root with only visible evidence.

    ``graphrag init`` is executed first so the upstream release supplies every
    prompt asset.  The generated settings are then replaced by the frozen,
    secret-free contract settings.  The root must not pre-exist: silently
    reusing a prior index, cache, or input is forbidden.
    """

    if run_root.exists():
        raise GraphRAGContractError("graphrag_run_root_must_not_exist")
    checkout = verify_upstream_checkout(upstream_checkout)
    settings = build_settings(
        completion_model=completion_model,
        embedding_model=embedding_model,
    )
    _run_upstream_command(
        [
            graphrag_executable,
            "init",
            "--root",
            str(run_root),
            "--force",
            "--model",
            completion_model,
            "--embedding",
            embedding_model,
        ]
    )
    settings_path = run_root / "settings.yaml"
    if not settings_path.is_file() or not (run_root / "prompts").is_dir():
        raise GraphRAGContractError("upstream_graphrag_init_artifacts_missing")
    # JSON is a strict YAML subset.  Canonical JSON avoids a dependency on a
    # second serializer and makes the frozen settings hash byte-for-byte clear.
    settings_path.write_bytes(_canonical_json(settings))
    input_metadata = materialize_visible_evidence(
        events,
        output_path=run_root / "input" / "visible_evidence.jsonl",
    )
    return {
        "run_root": str(run_root),
        "upstream": checkout,
        "contract_sha256": GraphRAGExecutionContract().sha256(),
        "settings_sha256": _sha256_file(settings_path),
        "input": input_metadata,
        "init_command": "graphrag init --root <run_root> --force --model <completion> --embedding <embedding>",
    }


def dry_validate_upstream_run_root(
    run_root: Path,
    *,
    graphrag_executable: str = "graphrag",
    api_base: str,
) -> None:
    """Exercise upstream config/index validation without an LLM request.

    The indexer receives a non-secret placeholder key and ``--dry-run`` plus
    ``--skip-validation``.  It may parse configuration and input but is not
    allowed to make completion or embedding calls.  A real execution must run
    its explicit probes and index/query ledger separately.
    """

    if not (run_root / "settings.yaml").is_file() or not (
        run_root / "input" / "visible_evidence.jsonl"
    ).is_file():
        raise GraphRAGContractError("graphrag_dry_validation_artifacts_missing")
    if not api_base:
        raise GraphRAGContractError("graphrag_api_base_required")
    environment = dict(os.environ)
    environment.update(
        {
            "GRAPHRAG_API_BASE": api_base,
            "GRAPHRAG_API_KEY": "dry-run-no-provider-call",
        }
    )
    _run_upstream_command(
        [
            graphrag_executable,
            "index",
            "--root",
            str(run_root),
            "--dry-run",
            "--skip-validation",
            "--no-cache",
        ],
        environment=environment,
    )


def _visible_event_document(event: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "evidence_id",
        "resource_type",
        "status",
        "codes",
        "valid_at",
        "known_at",
        "encounter_reference",
        "relation",
    }
    unexpected = set(event) - allowed
    if unexpected:
        raise GraphRAGContractError(
            f"visible_evidence_contains_unapproved_fields:{sorted(unexpected)}"
        )
    evidence_id = event.get("evidence_id")
    if not isinstance(evidence_id, str) or not evidence_id:
        raise GraphRAGContractError("visible_evidence_id_required")
    factual = {key: event.get(key) for key in sorted(allowed)}
    # The upstream input is plain evidence, not a solver packet.  In
    # particular it carries no target, predicate, expected decision or label.
    return {
        "id": evidence_id,
        "text": json.dumps(factual, sort_keys=True, separators=(",", ":")),
        "metadata": {
            "evidence_id": evidence_id,
            "valid_at": event.get("valid_at"),
            "known_at": event.get("known_at"),
            "resource_type": event.get("resource_type"),
        },
    }


def materialize_visible_evidence(
    events: list[dict[str, Any]], *, output_path: Path
) -> dict[str, Any]:
    """Serialize only already-disclosed evidence into GraphRAG's JSONL input."""

    if output_path.exists():
        raise GraphRAGContractError("graphrag_input_output_must_not_exist")
    documents = [_visible_event_document(event) for event in events]
    if len({document["id"] for document in documents}) != len(documents):
        raise GraphRAGContractError("duplicate_evidence_id_in_graphrag_input")
    documents.sort(key=lambda document: str(document["id"]))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(
        b"".join(_canonical_json(document) + b"\n" for document in documents)
    )
    return {
        "schema_version": "glhs-bench-graphrag-input.v1",
        "document_count": len(documents),
        "input_sha256": _sha256_file(output_path),
    }


def _git(path: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(path), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise GraphRAGContractError("upstream_checkout_unverifiable") from exc


def verify_upstream_checkout(path: Path) -> dict[str, str]:
    """Verify source origin and immutable commit of the official implementation."""

    if not (path / "packages" / "graphrag" / "graphrag").is_dir():
        raise GraphRAGContractError("upstream_graphrag_source_layout_invalid")
    commit = _git(path, "rev-parse", "HEAD")
    remote = _git(path, "remote", "get-url", "origin")
    if commit != UPSTREAM_COMMIT:
        raise GraphRAGContractError("upstream_graphrag_commit_mismatch")
    if remote.rstrip("/") not in {
        UPSTREAM_REPOSITORY.removesuffix(".git"),
        UPSTREAM_REPOSITORY,
    }:
        raise GraphRAGContractError("upstream_graphrag_origin_mismatch")
    return {"upstream_commit": commit, "upstream_origin": remote}


def validate_execution_manifest(
    manifest_path: Path,
    *,
    input_path: Path,
    settings: dict[str, Any],
    upstream_checkout: Path,
) -> dict[str, Any]:
    """Validate a real upstream index/query ledger, failing closed on gaps."""

    if not manifest_path.is_file() or not input_path.is_file():
        raise GraphRAGContractError("graphrag_execution_artifacts_missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise GraphRAGContractError("graphrag_execution_manifest_schema_invalid")
    contract = GraphRAGExecutionContract()
    if manifest.get("contract_sha256") != contract.sha256():
        raise GraphRAGContractError("graphrag_execution_contract_drift")
    if manifest.get("input_sha256") != _sha256_file(input_path):
        raise GraphRAGContractError("graphrag_execution_input_drift")
    if manifest.get("settings_sha256") != _sha256_bytes(_canonical_json(settings)):
        raise GraphRAGContractError("graphrag_execution_settings_drift")
    checkout = verify_upstream_checkout(upstream_checkout)
    if manifest.get("upstream") != checkout:
        raise GraphRAGContractError("graphrag_execution_upstream_drift")
    required = {
        "index_command": contract.index_command,
        "query_command": contract.query_command,
        "completion_probe": "PASS",
        "embedding_probe": "PASS",
        "index_status": "PASS",
        "query_status": "PASS",
        "output_sha256": None,
    }
    for key, expected in required.items():
        value = manifest.get(key)
        if expected is None:
            if not isinstance(value, dict) or not value:
                raise GraphRAGContractError(f"graphrag_execution_{key}_missing")
        elif value != expected:
            raise GraphRAGContractError(f"graphrag_execution_{key}_invalid")
    return manifest
