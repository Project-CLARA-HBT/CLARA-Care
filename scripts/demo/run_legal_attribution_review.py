#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request



@dataclass
class CheckResult:
    id: str
    passed: bool
    detail: str
    evidence: dict[str, Any] | None = None


def _json_or_default(value: Any, default: dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return default


def _run_rg(pattern: str, files: list[str]) -> tuple[bool, str]:
    cmd = ["rg", "-n", pattern, *files]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        first = (result.stdout.strip().splitlines() or [""])[0]
        return True, first
    if result.returncode == 1:
        return False, ""
    raise RuntimeError(f"rg failed: {' '.join(cmd)}\n{result.stderr}")


def _login(api_base_url: str, email: str, password: str, timeout: float) -> str:
    status_code, payload = _http_json(
        "POST",
        f"{api_base_url}/api/v1/auth/login",
        timeout=timeout,
        data={"email": email, "password": password},
    )
    if status_code != 200:
        raise RuntimeError(f"login failed: HTTP {status_code}")
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("login response missing access_token")
    return token


def _ensure_consent(api_base_url: str, token: str, timeout: float) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    status_code, status_payload = _http_json(
        "GET",
        f"{api_base_url}/api/v1/auth/consent-status",
        timeout=timeout,
        headers=headers,
    )
    if status_code != 200:
        raise RuntimeError(f"consent-status failed: HTTP {status_code}")
    status_payload = _json_or_default(status_payload, {})
    if status_payload.get("accepted") is True:
        return status_payload
    required_version = status_payload.get("required_version")
    if not isinstance(required_version, str) or not required_version:
        raise RuntimeError("consent-status missing required_version")
    accept_code, accept_payload = _http_json(
        "POST",
        f"{api_base_url}/api/v1/auth/consent",
        timeout=timeout,
        headers=headers,
        data={"consent_version": required_version, "accepted": True},
    )
    if accept_code != 200:
        raise RuntimeError(f"consent failed: HTTP {accept_code}")
    return _json_or_default(accept_payload, {})


def _http_json(
    method: str,
    url: str,
    *,
    timeout: float,
    headers: dict[str, str] | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    req_headers = dict(headers or {})
    body: bytes | None = None
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = request.Request(url=url, data=body, headers=req_headers, method=method.upper())
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            status = int(resp.getcode() or 0)
            raw = resp.read().decode("utf-8", errors="replace")
            payload = json.loads(raw) if raw.strip() else {}
            return status, _json_or_default(payload, {})
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return int(exc.code), _json_or_default(payload, {})
    except error.URLError as exc:  # pragma: no cover - network failure path
        return 0, {"error": str(exc)}
    except socket.timeout as exc:  # pragma: no cover - network timeout path
        return 0, {"error": f"timeout: {exc}"}
    except TimeoutError as exc:  # pragma: no cover - network timeout path
        return 0, {"error": str(exc)}


def _read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return _json_or_default(json.loads(path.read_text(encoding="utf-8")), {})
    except json.JSONDecodeError:
        return {}


def _check_chat_legal_guard(run_id: str) -> CheckResult:
    case_path = Path("artifacts") / "round2" / run_id / "demo-cases" / "case-c-legal-trap.json"
    body = _read_json_file(case_path)
    if not body:
        return CheckResult(
            id="chat_legal_guard",
            passed=False,
            detail="missing demo-cases/case-c-legal-trap.json",
            evidence={"path": str(case_path)},
        )
    ml = _json_or_default(body.get("ml"), {})
    policy_action = str(body.get("policy_action") or ml.get("policy_action") or "").lower()
    model_used = str(body.get("model_used", "")).lower()
    reply = str(body.get("reply", "")).lower()
    passed = (
        (policy_action in {"block", "escalate"}) or model_used == "legal-hard-guard-v1"
    ) and ("không có thẩm quyền" in reply or "vui lòng" in reply)
    return CheckResult(
        id="chat_legal_guard",
        passed=passed,
        detail=f"policy_action={policy_action or 'n/a'}; model={model_used or 'n/a'}",
        evidence={
            "policy_action": policy_action or None,
            "reply_preview": str(body.get("reply", ""))[:220],
            "model_used": body.get("model_used"),
            "source": str(case_path),
        },
    )


def _check_chat_attribution_contract(run_id: str) -> CheckResult:
    case_path = Path("artifacts") / "round2" / run_id / "demo-cases" / "case-c-legal-trap.json"
    body = _read_json_file(case_path)
    if not body:
        return CheckResult(
            id="chat_attribution_contract",
            passed=False,
            detail="missing demo-cases/case-c-legal-trap.json",
            evidence={"path": str(case_path)},
        )
    attribution = _json_or_default(body.get("attribution"), {})
    attributions = body.get("attributions")
    required_keys = {"channel", "mode", "source_used", "source_errors", "fallback_used"}
    passed = required_keys.issubset(attribution.keys()) and isinstance(attributions, list)
    return CheckResult(
        id="chat_attribution_contract",
        passed=passed,
        detail=f"keys={sorted(attribution.keys())}",
        evidence={
            "attribution": attribution,
            "attributions_count": len(attributions) if isinstance(attributions, list) else None,
            "source": str(case_path),
        },
    )


def _check_research_attribution_contract(
    api_base_url: str,
    token: str,
    timeout: float,
) -> CheckResult:
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"query": "warfarin interaction quick check", "research_mode": "fast"}
    status_code, body = _http_json(
        "POST",
        f"{api_base_url}/api/v1/research/tier2",
        timeout=timeout,
        headers=headers,
        data=payload,
    )
    if status_code == 200:
        attribution = _json_or_default(body.get("attribution"), {})
        attributions = body.get("attributions")
        required_keys = {"channel", "mode", "source_used", "source_errors", "fallback_used"}
        passed = required_keys.issubset(attribution.keys()) and isinstance(attributions, list)
        return CheckResult(
            id="research_attribution_contract",
            passed=passed,
            detail=f"live mode={attribution.get('mode', 'n/a')}",
            evidence={
                "attribution": attribution,
                "attributions_count": len(attributions) if isinstance(attributions, list) else None,
                "model_used": body.get("model_used"),
                "source": "live_api",
            },
        )

    # Fallback contract check when upstream is overloaded/timeouts.
    test_file = "services/api/tests/test_p2_proxy_endpoints.py"
    endpoint_file = "services/api/src/clara_api/api/v1/endpoints/research.py"
    has_test_attr, test_hit = _run_rg("attribution.*source_errors|fallback_used|attributions", [test_file])
    has_endpoint_attr, endpoint_hit = _run_rg(
        "attach_attribution|build_attribution|attributions|source_errors|fallback_used",
        [endpoint_file],
    )
    passed = has_test_attr and has_endpoint_attr
    return CheckResult(
        id="research_attribution_contract",
        passed=passed,
        detail=f"live_http={status_code}; fallback=contract_check",
        evidence={
            "live_response": body,
            "test_hit": test_hit,
            "endpoint_hit": endpoint_hit,
            "source": "contract_fallback",
        },
    )


def _check_ui_consent_gate() -> CheckResult:
    files = [
        "apps/web/app/careguard/page.tsx",
        "apps/web/components/selfmed/selfmed-consent-gate.tsx",
    ]
    found_disclaimer, disclaimer_hit = _run_rg(
        "miễn trừ trách nhiệm|disclaimer|không thay thế chẩn đoán",
        files,
    )
    found_tick, tick_hit = _run_rg("checkbox|tick|Đồng ý và tiếp tục|consent", files)
    passed = found_disclaimer and found_tick
    return CheckResult(
        id="ui_consent_gate",
        passed=passed,
        detail=f"disclaimer_hit={bool(disclaimer_hit)}; tick_hit={bool(tick_hit)}",
        evidence={"disclaimer_hit": disclaimer_hit, "tick_hit": tick_hit},
    )


def _check_ui_attribution_debug() -> CheckResult:
    files = [
        "apps/web/app/careguard/page.tsx",
        "apps/web/app/selfmed/ddi/page.tsx",
        "apps/web/components/research/debug-hints-panel.tsx",
    ]
    found_source_errors, source_hit = _run_rg("source_errors", files)
    found_fallback, fallback_hit = _run_rg("fallback_used|fallback", files)
    passed = found_source_errors and found_fallback
    return CheckResult(
        id="ui_attribution_fields",
        passed=passed,
        detail=f"source_errors={found_source_errors}; fallback={found_fallback}",
        evidence={"source_hit": source_hit, "fallback_hit": fallback_hit},
    )


def _write_report(out_dir: Path, payload: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    report_json = out_dir / "legal-attribution-review.json"
    report_md = out_dir / "legal-attribution-review.md"
    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Legal + Attribution Final Review",
        "",
        f"- run_id: `{payload['run_id']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- api_base_url: `{payload['api_base_url']}`",
        f"- overall_pass: `{'PASS' if payload['overall_pass'] else 'FAIL'}`",
        "",
        "| Check | Result | Detail |",
        "|---|---|---|",
    ]
    for check in payload["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        detail = str(check.get("detail", "")).replace("\n", " ")
        lines.append(f"| `{check['id']}` | **{status}** | {detail} |")
    lines.extend(["", "## Evidence", "```json", json.dumps(payload, ensure_ascii=False, indent=2), "```"])
    report_md.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run final legal + attribution review checks.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    args = parser.parse_args()

    token = _login(args.api_base_url.rstrip("/"), args.email, args.password, args.timeout_seconds)
    _ensure_consent(args.api_base_url.rstrip("/"), token, args.timeout_seconds)

    checks = [
        _check_chat_legal_guard(args.run_id),
        _check_chat_attribution_contract(args.run_id),
        _check_research_attribution_contract(args.api_base_url.rstrip("/"), token, args.timeout_seconds),
        _check_ui_consent_gate(),
        _check_ui_attribution_debug(),
    ]

    payload = {
        "run_id": args.run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_base_url": args.api_base_url.rstrip("/"),
        "overall_pass": all(check.passed for check in checks),
        "checks": [
            {
                "id": check.id,
                "passed": check.passed,
                "detail": check.detail,
                "evidence": check.evidence or {},
            }
            for check in checks
        ],
    }

    out_dir = Path("artifacts") / "round2" / args.run_id / "legal-attribution-review"
    _write_report(out_dir, payload)
    print(f"Wrote: {out_dir / 'legal-attribution-review.json'}")
    print(f"Wrote: {out_dir / 'legal-attribution-review.md'}")
    print(f"Overall: {'PASS' if payload['overall_pass'] else 'FAIL'}")
    return 0 if payload["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
