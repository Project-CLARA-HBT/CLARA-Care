#!/usr/bin/env python3
"""Fail if any Alembic migration module lacks a ``downgrade()``.

Spec: ``clara-platform-hardening`` · Task 10.2 (companion to the pre-migration
backup step in ``.github/workflows/cd.yml``). This is the deploy-time gate that
enforces design Property 23 / Requirement 9.3: *every migration to be deployed
must define a downgrade* so a failed migration can be rolled back per the
``docs/runbooks/backup-restore.md`` "Pre-migration backup & rollback" section.

The check is static and dependency-free (stdlib ``ast`` only) so it runs on a CI
runner without importing the application or its database drivers:

* It scans every revision module under the given Alembic ``versions``
  directory (defaulting to ``services/api/alembic/versions``).
* A module **fails** the check when it does not define a module-level
  ``downgrade`` function (it "lacks a downgrade()").
* A module emits a **warning** (non-fatal by default) when ``downgrade()`` is a
  no-op (only ``pass``/``...``/a docstring), since that cannot actually roll the
  schema back. Pass ``--strict`` to also fail on no-op downgrades.

Exit code is ``0`` when every migration defines a downgrade, ``1`` otherwise.
No secret values or PII are read or emitted — it only inspects source files.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

DEFAULT_VERSIONS_DIR = Path("services/api/alembic/versions")


def _find_function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node  # type: ignore[return-value]
    return None


def _is_noop_body(func: ast.FunctionDef) -> bool:
    """Return True when the function body does nothing meaningful.

    A body counts as a no-op when, after dropping a leading docstring, every
    remaining statement is ``pass`` or a bare ``...`` expression.
    """
    body = list(func.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]  # drop docstring
    if not body:
        return True
    for stmt in body:
        if isinstance(stmt, ast.Pass):
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) \
                and stmt.value.value is Ellipsis:
            continue
        return False
    return True


def check_versions(versions_dir: Path, strict: bool = False) -> int:
    if not versions_dir.is_dir():
        print(f"[error] migration versions directory not found: {versions_dir}", file=sys.stderr)
        return 1

    files = sorted(p for p in versions_dir.glob("*.py") if p.name != "__init__.py")
    if not files:
        print(f"[error] no migration modules found under {versions_dir}", file=sys.stderr)
        return 1

    missing: list[str] = []
    noop: list[str] = []
    ok = 0

    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:  # pragma: no cover - defensive
            print(f"[error] could not parse {path}: {exc}", file=sys.stderr)
            return 1

        func = _find_function(tree, "downgrade")
        if func is None:
            missing.append(path.name)
        elif _is_noop_body(func):
            noop.append(path.name)
        else:
            ok += 1

    print(f"[migration-downgrade-check] scanned {len(files)} migration(s) in {versions_dir}")
    print(f"[migration-downgrade-check] {ok} define a non-empty downgrade()")

    for name in noop:
        print(f"[warn] {name}: downgrade() is a no-op (cannot roll the schema back)")

    if missing:
        for name in missing:
            print(f"[error] {name}: missing a downgrade() — migration cannot be rolled back", file=sys.stderr)
        print(
            f"[migration-downgrade-check] FAILED: {len(missing)} migration(s) lack a downgrade()",
            file=sys.stderr,
        )
        return 1

    if strict and noop:
        print(
            f"[migration-downgrade-check] FAILED (--strict): {len(noop)} migration(s) have a no-op downgrade()",
            file=sys.stderr,
        )
        return 1

    print("[migration-downgrade-check] OK: every migration defines a downgrade()")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "versions_dir",
        nargs="?",
        default=str(DEFAULT_VERSIONS_DIR),
        help="Path to the Alembic versions directory",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Also fail when a downgrade() exists but is a no-op (pass/...)",
    )
    args = parser.parse_args(argv)
    return check_versions(Path(args.versions_dir), strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
