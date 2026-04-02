#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export production flow-events and normalize into mining-friendly JSON."
    )
    parser.add_argument(
        "--api-base",
        required=True,
        help="API base URL, e.g. https://clara.thiennn.icu",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output JSON file path.",
    )
    parser.add_argument("--limit", type=int, default=500, help="Max events to fetch.")
    parser.add_argument(
        "--source",
        default="research",
        help="Flow source filter (default: research).",
    )
    parser.add_argument("--token", default="", help="Optional bearer token.")
    parser.add_argument("--email", default="", help="Login email if token missing.")
    parser.add_argument("--password", default="", help="Login password if token missing.")
    parser.add_argument("--timeout", type=float, default=12.0)
    return parser.parse_args()


def _join(base: str, path: str) -> str:
    return base.rstrip("/") + "/" + path.lstrip("/")


def _request_json(
    *,
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 12.0,
) -> dict[str, Any]:
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url=url, data=body, method=method.upper(), headers=req_headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
        raw = response.read().decode("utf-8", errors="replace")
    parsed = json.loads(raw) if raw else {}
    if not isinstance(parsed, dict):
        return {"data": parsed}
    return parsed


def _ensure_token(args: argparse.Namespace) -> str:
    if str(args.token or "").strip():
        return str(args.token).strip()
    if not (str(args.email or "").strip() and str(args.password or "").strip()):
        raise RuntimeError("Missing token and login credentials.")
    login = _request_json(
        method="POST",
        url=_join(args.api_base, "/api/v1/auth/login"),
        payload={"email": args.email, "password": args.password},
        timeout=args.timeout,
    )
    token = str(login.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("Login succeeded but access_token missing.")
    return token


def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    event = item.get("event")
    event_obj = event if isinstance(event, dict) else {}
    source_errors = event_obj.get("source_errors")
    fallback_reason = event_obj.get("fallback_reason")
    fallback_used = bool(event_obj.get("fallback_used"))
    unsupported_claims = event_obj.get("unsupported_claims")
    verification_matrix = event_obj.get("verification_matrix")
    query = str(event_obj.get("query") or "").strip()
    return {
        "sequence": item.get("sequence"),
        "timestamp": item.get("timestamp"),
        "source": item.get("source"),
        "user_id": item.get("user_id"),
        "role": item.get("role"),
        "intent": item.get("intent"),
        "model_used": item.get("model_used"),
        "query": query,
        "source_errors": source_errors,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "unsupported_claims": unsupported_claims,
        "verification_matrix": verification_matrix,
        "response_summary": {
            "metadata": {
                "source_errors": source_errors,
                "fallback_reason": fallback_reason,
                "fallback_used": fallback_used,
                "unsupported_claims": unsupported_claims,
            }
        },
        "event": event_obj,
    }


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    try:
        token = _ensure_token(args)
        query = urllib.parse.urlencode(
            {
                "limit": max(1, min(int(args.limit), 500)),
                "source": str(args.source or "research").strip(),
            }
        )
        payload = _request_json(
            method="GET",
            url=_join(args.api_base, f"/api/v1/system/flow-events?{query}"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=args.timeout,
        )
        raw_items = payload.get("items")
        items = [row for row in raw_items if isinstance(row, dict)] if isinstance(raw_items, list) else []
        normalized = [_normalize_item(row) for row in items]
        output = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "api_base": args.api_base.rstrip("/"),
            "source": str(args.source or "research").strip(),
            "count": len(normalized),
            "items": normalized,
            "latest_sequence": payload.get("latest_sequence"),
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("[export-production-flow-events] ok")
        print(f"- source: {output['source']}")
        print(f"- count: {output['count']}")
        print(f"- output: {output_path}")
        return 0
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        print(f"[export-production-flow-events] http_error:{exc.code}: {details}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"[export-production-flow-events] failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
