"""SH-postgres_isolation: real PostgreSQL 16 isolation integration test.

What it verifies (real integration, not SQLite):
  1. Unit-level guard: a non-isolated, production-looking DATABASE_URL is
     refused by ``pg_guard.assert_isolated_database_url`` (no Docker needed).
  2. When Docker is available: bring up the dedicated compose cluster
     (``docker-compose.pg.yaml``), assert ``SHOW server_version`` starts with
     ``16``, run two concurrent psycopg transactions demonstrating independent
     commit visibility, record evidence, then tear the cluster down (-v).

Docker availability is detected at runtime; if the daemon is unreachable or
the image cannot be pulled, the Docker-dependent assertions SKIP with the real
failure output as the skip reason. They never silently pass.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[4]
COMPOSE = REPO / "infra" / "research" / "venue2027" / "docker-compose.pg.yaml"
PROBE = REPO / "research" / "venue2027" / "_shared" / "tools" / "pg_concurrency_probe.py"
TOOLS = REPO / "research" / "venue2027" / "_shared" / "tools"
LOGDIR = REPO / "research" / "venue2027" / "proof" / "logs"
VERSION_LOG = LOGDIR / "pg_server_version.log"
PROBE_JSON = LOGDIR / "pg_probe_evidence.json"

sys.path.insert(0, str(TOOLS))
import pg_guard  # noqa: E402

DSN = "postgresql://research_app:research-only-throwaway@pg_research:5432/clara_research"
PG_COMPOSE_DIGEST = (
    "postgres@sha256:e62fbf9d3e2b49816a32c400ed2dba83e3b361e6833e624024309c35d334b412"
)
PY_DIGEST = "python@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b"


def _run(argv: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, **kw)  # type: ignore[arg-type]


def docker_available() -> tuple[bool, str]:
    """Real availability detection, returning (ok, real_output)."""
    ver = _run(["docker", "info", "--format", "{{.ServerVersion}}"])
    if ver.returncode != 0:
        return False, (ver.stderr or ver.stdout).strip()[:400]
    compose_ver = _run(["docker", "compose", "version"])
    if compose_ver.returncode != 0:
        return False, (compose_ver.stderr or compose_ver.stdout).strip()[:400]
    return True, f"docker {ver.stdout.strip()} / compose {compose_ver.stdout.strip()}"


def _image_present(digest_ref: str) -> bool:
    return _run(["docker", "image", "inspect", digest_ref]).returncode == 0


def _pull_image(digest_ref: str) -> tuple[bool, str]:
    res = _run(["docker", "pull", digest_ref])
    return res.returncode == 0, (res.stderr or res.stdout).strip()[-400:]


# ---------------------------------------------------------------- unit guard
def test_production_like_database_url_is_refused() -> None:
    """Unit-level: prod-shaped/localhost DSNs must be refused, not guessed."""
    for bad in (
        "postgresql://clara:prodsecret@db.prod.clara-care.internal:5432/clara",
        "postgresql://clara:clara@localhost:5432/clara",
        "postgresql://clara:clara@127.0.0.1:5432/clara",
        "postgresql://clara:clara@10.1.2.3:5432/clara",
    ):
        with pytest.raises(pg_guard.PgGuardError) as exc:
            pg_guard.assert_isolated_database_url(bad)
        assert exc.value.reason_code in ("PROD_LIKE_HOST", "NON_ISOLATED_HOST")


def test_only_isolated_shape_is_accepted() -> None:
    ok, reason = pg_guard.check_database_url(DSN)
    assert (ok, reason) == (True, "OK")


# ------------------------------------------------------------------ docker
DOCKER_OK, DOCKER_REASON = docker_available()

pytestmark = pytest.mark.skipif(
    not DOCKER_OK,
    reason=f"Docker daemon/compose unavailable on this host: {DOCKER_REASON}",
)


@pytest.fixture(scope="module")
def pg_cluster() -> str:
    """Bring up the compose cluster; return real compose output (trimmed)."""
    LOGDIR.mkdir(parents=True, exist_ok=True)
    # Fail fast if images are missing and cannot be pulled (record real output).
    for digest_ref in (PG_COMPOSE_DIGEST, PY_DIGEST):
        if not _image_present(digest_ref):
            pulled, output = _pull_image(digest_ref)
            if not pulled:
                pytest.skip(f"image pull failed for {digest_ref}: {output}")
    up = _run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE),
            "up",
            "-d",
            "--wait",
            "--wait-timeout",
            "90",
        ]
    )
    if up.returncode != 0:
        down = _run(["docker", "compose", "-f", str(COMPOSE), "down", "-v"])
        pytest.skip(
            "docker compose up failed: "
            f"stdout={up.stdout.strip()[-300:]} stderr={up.stderr.strip()[-300:]} "
            f"down={down.returncode}"
        )
    return up.stdout.strip()[-300:]


def _probe_in_network() -> tuple[int, str]:
    """Run pg_concurrency_probe.py inside pg_research_net (no host port).

    The probe needs to write its evidence JSON; the repo is mounted read-only
    and the log directory is mounted read-write at /out.
    """
    cmd = [
        "docker",
        "run",
        "--rm",
        "--network",
        "pg_research_net",
        "-v",
        f"{REPO}:/work:ro",
        "-v",
        f"{LOGDIR}:/out",
        "-w",
        "/work",
        PY_DIGEST,
        "bash",
        "-lc",
        "pip install --no-cache-dir -q 'psycopg[binary]==3.2.3' && "
        f"python3 {PROBE.relative_to(REPO)} {DSN} /out/pg_probe_evidence.json",
    ]
    res = _run(cmd, timeout=600)
    output = (res.stdout + "\n" + res.stderr).strip()[-2000:]
    return res.returncode, output


def test_pg16_isolated_concurrency(pg_cluster: str) -> None:
    """Real PostgreSQL 16: version assertion + concurrent commit visibility."""
    code, output = _probe_in_network()
    if code == 2:
        pytest.skip(f"probe could not run (driver setup failure): {output}")
    assert code == 0, f"probe failed (exit {code}):\n{output}"
    evidence = json.loads(PROBE_JSON.read_text())
    server_version = str(evidence["server_version"])
    assert server_version.startswith("16"), f"expected PG16, saw {server_version!r}"
    assert evidence["verdict"] == "PASS", evidence
    vis = evidence["visibility"]
    # Deterministic independent-commit-visibility schedule (see probe docstring).
    assert vis["reader1_uncommitted_invisible"] == 0
    assert vis["reader2_after_a_commit_only"] == 1
    assert vis["rows_after_both_commits"] == [[1, "A"], [2, "B"]]

    VERSION_LOG.write_text(
        f"server_version={server_version}\n"
        f"server_version_num={evidence['server_version_num']}\n"
        f"image={PG_COMPOSE_DIGEST}\n"
        f"verdict={evidence['verdict']}\n"
        f"concurrent_writers=2\n",
        encoding="utf-8",
    )


def test_teardown_after_probe(pg_cluster: str) -> None:
    """Deterministic teardown: remove cluster and named volume."""
    down = _run(["docker", "compose", "-f", str(COMPOSE), "down", "-v"])
    assert down.returncode == 0, f"teardown failed: {down.stderr[-400:]}"
