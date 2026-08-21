"""Batch HL7 FHIR validator wrapper pinned to the repo toolchain lock (H-002).

The version/checksum pin is read from
``docs/interoperability/fhir-toolchain.lock.json`` — the single source of truth
also used by ``scripts/validation/validate-lifemap-fhir.sh``. The JAR is never
downloaded into the repository: it is resolved from ``FHIR_VALIDATOR_JAR``, a
cache directory, or downloaded on demand to the cache and checksum-verified.

If the JAR is absent and cannot be downloaded, the wrapper records an honest
``execution: PENDING`` result instead of fabricating a validator run.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = REPO_ROOT / "docs" / "interoperability" / "fhir-toolchain.lock.json"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "clara-fhir-validator"

FHIR_VERSION_MODE = {
    "r4": "4.0.1",
    "stu3": "3.0.2",
}

_SEVERITY = re.compile(
    r"(?:\[(?P<bracket>Error|Warning|Information|Info|Hint|Fatal|Exception)\]"
    r"|:\s*(?P<line>Error|Warning|Information|Info|Hint|Fatal|Exception)\s+-)",
    re.IGNORECASE,
)
MAX_RECORDED_OUTPUT = 60_000


@dataclass(frozen=True)
class ValidatorPin:
    version: str
    artifact: str
    url: str
    sha256: str


def load_pin(lock_path: Path | None = None) -> ValidatorPin:
    """Read the validator pin from the repo toolchain lock file."""
    path = lock_path or LOCK_PATH
    with path.open("r", encoding="utf-8") as handle:
        lock = json.load(handle)
    validator = lock["validator"]
    return ValidatorPin(
        version=str(validator["version"]),
        artifact=str(validator["artifact"]),
        url=str(validator["url"]),
        sha256=str(validator["sha256"]),
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def java_available() -> bool:
    return shutil.which("java") is not None


def default_jar_path(cache_dir: Path | None = None) -> Path:
    return (cache_dir or DEFAULT_CACHE_DIR) / "validator_cli.jar"


def resolve_jar(
    jar_path: Path | str | None = None,
    *,
    allow_download: bool = True,
    cache_dir: Path | None = None,
) -> Path | None:
    """Resolve a verified validator JAR, or return ``None`` (PENDING)."""
    if jar_path:
        candidate = Path(jar_path)
        if candidate.is_file() and sha256_file(candidate) == load_pin().sha256:
            return candidate
        if candidate.is_file():
            raise RuntimeError(f"validator jar checksum mismatch for {candidate}; refusing to run")
    cached = default_jar_path(cache_dir)
    if cached.is_file() and sha256_file(cached) == load_pin().sha256:
        return cached
    if not allow_download:
        return None
    pin = load_pin()
    cache_dir_path = cached.parent
    cache_dir_path.mkdir(parents=True, exist_ok=True)
    try:
        download_jar(pin, cached)
    except (OSError, TimeoutError, urllib.error.URLError):  # pragma: no cover
        return None
    return cached if cached.is_file() else None


def download_jar(pin: ValidatorPin, destination: Path) -> Path:
    """Download and checksum-verify the pinned JAR into ``destination``."""
    request = urllib.request.Request(
        pin.url,
        headers={"User-Agent": "clara-fhir-conformance/1.0"},
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(
        prefix="validator_cli-", suffix=".jar", dir=destination.parent
    )
    os.close(tmp_fd)
    try:
        with (
            urllib.request.urlopen(request, timeout=600) as response,
            open(tmp_path, "wb") as handle,
        ):
            shutil.copyfileobj(response, handle)
        actual = sha256_file(Path(tmp_path))
        if actual != pin.sha256:
            raise RuntimeError(f"validator jar checksum mismatch after download: {actual}")
        os.replace(tmp_path, destination)
    finally:
        if Path(tmp_path).exists():
            Path(tmp_path).unlink()
    return destination


def _summarize(output: str) -> dict[str, int]:
    counts = {"fatal": 0, "error": 0, "warning": 0, "info": 0, "hint": 0}
    for match in _SEVERITY.finditer(output):
        key = (match.group("bracket") or match.group("line")).lower()
        if key == "information":
            key = "info"
        if key == "exception":
            key = "error"
        counts[key] += 1
    return counts


def validate_file(
    fixture: Path,
    mode: str,
    *,
    jar: Path | None = None,
    allow_download: bool = True,
) -> dict:
    """Validate one fixture with the pinned JAR in the given version mode."""
    if mode not in FHIR_VERSION_MODE:
        raise ValueError(f"unsupported mode {mode!r}; expected r4|stu3")
    pin = load_pin()
    payload_sha = sha256_file(fixture)
    resolved = resolve_jar(jar, allow_download=allow_download)
    if resolved is None or not java_available():
        return {
            "fixture": str(fixture),
            "payload_sha256": payload_sha,
            "execution": "PENDING",
            "validator_version": pin.version,
            "mode": mode,
            "fhir_version": FHIR_VERSION_MODE[mode],
            "exit_status": None,
            "messages": [],
            "severity": {},
            "structural": "not_executed",
            "reason": (
                "pinned validator JAR unavailable and could not be downloaded"
                if resolved is None
                else "java runtime unavailable"
            ),
        }
    command = [
        "java",
        "-jar",
        str(resolved),
        str(fixture),
        "-version",
        FHIR_VERSION_MODE[mode],
        "-tx",
        "n/a",
        "-output-style",
        "compact",
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    severity = _summarize(output)
    issue_lines = [
        line.strip() for line in output.splitlines() if _SEVERITY.search(line) or "Issue:" in line
    ]
    messages = (issue_lines + output.splitlines()[-3:])[:120]
    return {
        "fixture": str(fixture),
        "payload_sha256": payload_sha,
        "execution": "OK",
        "validator_version": pin.version,
        "mode": mode,
        "fhir_version": FHIR_VERSION_MODE[mode],
        "exit_status": completed.returncode,
        "messages": messages,
        "severity": severity,
        "structural": (
            "valid"
            if completed.returncode == 0 and severity["error"] + severity["fatal"] == 0
            else "error"
        ),
        "output_tail": output[-MAX_RECORDED_OUTPUT:],
    }


def batch(
    fixtures: list[tuple[Path, str]],
    *,
    jar: Path | None = None,
    allow_download: bool = True,
) -> dict:
    """Run the pinned validator over (fixture, mode) pairs."""
    pin = load_pin()
    jar_state = resolve_jar(jar, allow_download=allow_download)
    results = [
        validate_file(fixture, mode, jar=jar, allow_download=allow_download)
        for fixture, mode in fixtures
    ]
    executed = [r for r in results if r["execution"] == "OK"]
    return {
        "pin": {
            "version": pin.version,
            "artifact": pin.artifact,
            "url": pin.url,
            "sha256": pin.sha256,
        },
        "java_available": java_available(),
        "jar_available": jar_state is not None,
        "jar_sha256": sha256_file(jar_state) if jar_state is not None else None,
        "execution": "OK" if executed and len(executed) == len(results) else "PENDING",
        "results": results,
    }
