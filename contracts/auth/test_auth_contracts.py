"""Contract schema validation test for token contract and auth threat inventory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

CONTRACTS_DIR = Path(__file__).resolve().parent


def load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_token_contract_schema_structure() -> None:
    schema_path = CONTRACTS_DIR / "token-contract.schema.json"
    assert schema_path.exists(), f"Missing schema at {schema_path}"
    schema = load_json(schema_path)
    assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert "oneOf" in schema
    assert "$defs" in schema
    assert "AccessToken" in schema["$defs"]
    assert "RefreshToken" in schema["$defs"]

    access_props = schema["$defs"]["AccessToken"]["properties"]
    assert set(schema["$defs"]["AccessToken"]["required"]) == {
        "sub",
        "role",
        "exp",
        "iat",
        "iss",
        "jti",
        "typ",
    }
    assert access_props["typ"]["const"] == "access"

    refresh_props = schema["$defs"]["RefreshToken"]["properties"]
    assert set(schema["$defs"]["RefreshToken"]["required"]) == {
        "sub",
        "role",
        "exp",
        "iat",
        "iss",
        "jti",
        "typ",
    }
    assert refresh_props["typ"]["const"] == "refresh"


def test_auth_threat_inventory_schema_structure() -> None:
    schema_path = CONTRACTS_DIR / "auth-threat-inventory.schema.json"
    assert schema_path.exists(), f"Missing schema at {schema_path}"
    schema = load_json(schema_path)
    assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert "required" in schema
    expected_required = {
        "schema_version",
        "threat_model",
        "invariants",
        "endpoints_audited",
        "threat_vectors",
        "residual_risks",
    }
    assert expected_required.issubset(set(schema["required"]))
