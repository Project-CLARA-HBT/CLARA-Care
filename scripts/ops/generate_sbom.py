#!/usr/bin/env python3
"""Automated Software Bill of Materials (SBOM) generator for CLARA Care.

Spec: PH01 / A07 (Tests + CI)
Generates CycloneDX 1.5 JSON and CLARA Supply Chain Manifest across all
three active ecosystems in the repository:
  1. Python: services/api, services/ml, services/asr, services/ocr
  2. Node: apps/web
  3. Flutter / Dart: apps/mobile

The script uses standard library packages (tomllib, json, pathlib, hashlib,
datetime, urllib.parse) with graceful fallback parsing for YAML/pubspec if PyYAML
is not present, ensuring hermetic zero-dependency execution.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import tomllib
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


@dataclass
class Component:
    name: str
    version: str
    ecosystem: str  # "pypi", "npm", "pub"
    purl: str
    surface: str  # "services/api", "services/ml", "services/asr", "services/ocr", "apps/web", "apps/mobile"
    scope: str = "required"  # "required" (runtime) or "optional" (dev)
    direct: bool = False
    constraint: str = ""
    pinned: bool = True
    integrity_hash: str = ""
    hash_algorithm: str = ""
    license: str = ""
    dependencies: list[str] = field(default_factory=list)

    def to_cyclonedx(self) -> dict[str, Any]:
        comp: dict[str, Any] = {
            "bom-ref": self.purl,
            "type": "library",
            "name": self.name,
            "version": self.version,
            "purl": self.purl,
            "scope": self.scope,
            "properties": [
                {"name": "clara:ecosystem", "value": self.ecosystem},
                {"name": "clara:surface", "value": self.surface},
                {"name": "clara:direct", "value": str(self.direct).lower()},
                {"name": "clara:pinned", "value": str(self.pinned).lower()},
            ],
        }
        if self.constraint:
            comp["properties"].append({"name": "clara:constraint", "value": self.constraint})
        if self.license:
            comp["licenses"] = [{"license": {"id": self.license}}]
        if self.integrity_hash and self.hash_algorithm:
            comp["hashes"] = [
                {
                    "alg": self.hash_algorithm,
                    "content": self.integrity_hash,
                }
            ]
        return comp


def make_purl(ecosystem: str, name: str, version: str) -> str:
    """Format Package URL (purl) per standard spec."""
    if ecosystem == "npm":
        if name.startswith("@") and "/" in name:
            scope, pkg = name.split("/", 1)
            return f"pkg:npm/{quote(scope)}/{quote(pkg)}@{version}"
        return f"pkg:npm/{quote(name)}@{version}"
    elif ecosystem == "pypi":
        return f"pkg:pypi/{quote(name.lower())}@{version}"
    elif ecosystem == "pub":
        return f"pkg:pub/{quote(name)}@{version}"
    return f"pkg:generic/{quote(name)}@{version}"


def is_constraint_pinned(constraint: str) -> bool:
    """Determine if a declared dependency constraint is strictly pinned to a single version."""
    if not constraint:
        return False
    c = constraint.strip()
    if c == "*" or c.lower() == "any":
        return False
    if c.startswith("^") or c.startswith("~") or c.startswith(">") or c.startswith("<"):
        return False
    if "==" in c:
        return True
    # In package.json, an exact semver like "18.3.1" or "15.5.22" without prefix is pinned
    if re.match(r"^\d+\.\d+\.\d+.*$", c):
        return True
    return False


def _parse_yaml_fallback(text: str) -> dict[str, Any]:
    """Minimal fallback parser for simple pubspec YAML structures when PyYAML is unavailable."""
    result: dict[str, Any] = {"packages": {}, "dependencies": {}, "dev_dependencies": {}}
    current_section = ""
    current_pkg = ""

    for line in text.splitlines():
        raw = line.split("#", 1)[0].rstrip()
        if not raw:
            continue
        indent = len(raw) - len(raw.lstrip())
        stripped = raw.strip()

        if indent == 0 and stripped.endswith(":"):
            current_section = stripped[:-1].strip()
            current_pkg = ""
            continue

        if current_section == "packages":
            if indent == 2 and stripped.endswith(":"):
                current_pkg = stripped[:-1].strip()
                result["packages"][current_pkg] = {}
            elif indent >= 4 and current_pkg:
                parts = stripped.split(":", 1)
                if len(parts) == 2:
                    k = parts[0].strip()
                    v = parts[1].strip().strip('"').strip("'")
                    if k in ("version", "dependency", "source"):
                        result["packages"][current_pkg][k] = v
                    elif k == "sha256":
                        result["packages"][current_pkg].setdefault("description", {})["sha256"] = v
        elif current_section in ("dependencies", "dev_dependencies"):
            if indent == 2:
                parts = stripped.split(":", 1)
                if len(parts) == 2:
                    k = parts[0].strip()
                    v = parts[1].strip()
                    result[current_section][k] = v

    return result


class SbomBuilder:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.components: list[Component] = []
        self.dependencies_graph: dict[str, list[str]] = {}
        self.missing_lockfiles: list[str] = []

    def scan_all(self) -> None:
        self.scan_python_api()
        self.scan_python_ml()
        self.scan_python_asr()
        self.scan_python_ocr()
        self.scan_node_web()
        self.scan_flutter_mobile()

    def scan_python_service(self, surface: str) -> None:
        proj_path = self.repo_root / surface / "pyproject.toml"
        lock_path = self.repo_root / surface / "uv.lock"

        if not proj_path.is_file():
            return

        with open(proj_path, "rb") as f:
            proj_data = tomllib.load(f)

        project_section = proj_data.get("project", {})
        direct_runtime_specs = project_section.get("dependencies", [])
        direct_dev_specs = project_section.get("optional-dependencies", {}).get("dev", [])

        # Parse direct specs into mapping: name -> constraint
        direct_constraints: dict[str, str] = {}
        direct_scope: dict[str, str] = {}

        def parse_dep_spec(spec: str, scope: str) -> None:
            # Handle extras like psycopg[binary]>=3.2.3 or markers like python-jose[cryptography]>=3.4.0
            spec_clean = spec.split(";")[0].strip()
            match = re.match(r"^([A-Za-z0-9_.\-]+)(?:\[[^\]]+\])?(.*)$", spec_clean)
            if match:
                pkg_name = match.group(1).lower().replace("_", "-")
                constraint = match.group(2).strip()
                direct_constraints[pkg_name] = constraint
                direct_scope[pkg_name] = scope

        for s in direct_runtime_specs:
            parse_dep_spec(s, "required")
        for s in direct_dev_specs:
            parse_dep_spec(s, "optional")

        if not lock_path.is_file():
            self.missing_lockfiles.append(f"{surface}/uv.lock")
            # Fallback to direct dependencies without lockfile
            for pkg_name, constraint in direct_constraints.items():
                ver = constraint.lstrip("=>~^<") if constraint else "unpinned"
                purl = make_purl("pypi", pkg_name, ver)
                comp = Component(
                    name=pkg_name,
                    version=ver,
                    ecosystem="pypi",
                    purl=purl,
                    surface=surface,
                    scope=direct_scope.get(pkg_name, "required"),
                    direct=True,
                    constraint=constraint,
                    pinned=is_constraint_pinned(constraint),
                )
                self.components.append(comp)
            return

        with open(lock_path, "rb") as f:
            lock_data = tomllib.load(f)

        locked_packages = lock_data.get("package", [])
        for pkg in locked_packages:
            name = pkg.get("name", "").lower().replace("_", "-")
            version = pkg.get("version", "")
            if not name or not version:
                continue

            purl = make_purl("pypi", name, version)
            is_direct = name in direct_constraints
            constraint = direct_constraints.get(name, "")
            scope = direct_scope.get(name, "required")

            # Extract hash: prefer sdist sha256 or first wheel sha256
            integrity_hash = ""
            hash_alg = ""
            sdist_hash = pkg.get("sdist", {}).get("hash", "")
            if sdist_hash and ":" in sdist_hash:
                alg, h = sdist_hash.split(":", 1)
                integrity_hash = h
                hash_alg = "SHA-256" if alg.lower() == "sha256" else alg.upper()
            elif pkg.get("wheels"):
                wheel_hash = pkg["wheels"][0].get("hash", "")
                if wheel_hash and ":" in wheel_hash:
                    alg, h = wheel_hash.split(":", 1)
                    integrity_hash = h
                    hash_alg = "SHA-256" if alg.lower() == "sha256" else alg.upper()

            deps = [d.get("name", "").lower().replace("_", "-") for d in pkg.get("dependencies", []) if d.get("name")]

            comp = Component(
                name=name,
                version=version,
                ecosystem="pypi",
                purl=purl,
                surface=surface,
                scope=scope,
                direct=is_direct,
                constraint=constraint,
                pinned=is_constraint_pinned(constraint) if is_direct else True,
                integrity_hash=integrity_hash,
                hash_algorithm=hash_alg,
                dependencies=deps,
            )
            self.components.append(comp)

            # Record dependency graph
            dep_purls = [make_purl("pypi", d, "") for d in deps]
            self.dependencies_graph[purl] = dep_purls

    def scan_python_api(self) -> None:
        self.scan_python_service("services/api")

    def scan_python_ml(self) -> None:
        self.scan_python_service("services/ml")

    def scan_python_asr(self) -> None:
        proj_path = self.repo_root / "services/asr" / "pyproject.toml"
        if not proj_path.is_file():
            return
        with open(proj_path, "rb") as f:
            data = tomllib.load(f)
        deps = data.get("project", {}).get("dependencies", [])
        lock_path = self.repo_root / "services/asr" / "uv.lock"
        if not lock_path.is_file():
            self.missing_lockfiles.append("services/asr/uv.lock")

        for s in deps:
            parts = s.split("==")
            if len(parts) == 2:
                name = parts[0].strip().lower().replace("_", "-")
                ver = parts[1].strip()
                purl = make_purl("pypi", name, ver)
                comp = Component(
                    name=name,
                    version=ver,
                    ecosystem="pypi",
                    purl=purl,
                    surface="services/asr",
                    scope="required",
                    direct=True,
                    constraint=f"=={ver}",
                    pinned=True,
                )
                self.components.append(comp)

    def scan_python_ocr(self) -> None:
        dockerfile = self.repo_root / "services/ocr" / "Dockerfile"
        if not dockerfile.is_file():
            return
        text = dockerfile.read_text(encoding="utf-8")
        # Look for pip install lines
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("RUN pip install"):
                # Missing lockfile
                self.missing_lockfiles.append("services/ocr/Dockerfile (direct unpinned pip install)")
                tokens = line.split()
                # filter flags
                pkgs = [t for t in tokens if not t.startswith("-") and t not in ("RUN", "pip", "install")]
                for p in pkgs:
                    name = p.lower().replace("_", "-")
                    purl = make_purl("pypi", name, "unpinned")
                    comp = Component(
                        name=name,
                        version="unpinned",
                        ecosystem="pypi",
                        purl=purl,
                        surface="services/ocr",
                        scope="required",
                        direct=True,
                        constraint="unpinned",
                        pinned=False,
                    )
                    self.components.append(comp)

    def scan_node_web(self) -> None:
        pkg_path = self.repo_root / "apps/web" / "package.json"
        lock_path = self.repo_root / "apps/web" / "package-lock.json"

        if not pkg_path.is_file():
            return

        with open(pkg_path, encoding="utf-8") as f:
            pkg_data = json.load(f)

        direct_deps = pkg_data.get("dependencies", {})
        direct_dev_deps = pkg_data.get("devDependencies", {})

        if not lock_path.is_file():
            self.missing_lockfiles.append("apps/web/package-lock.json")
            for name, constraint in direct_deps.items():
                ver = constraint.lstrip("^~>=")
                purl = make_purl("npm", name, ver)
                self.components.append(
                    Component(
                        name=name,
                        version=ver,
                        ecosystem="npm",
                        purl=purl,
                        surface="apps/web",
                        scope="required",
                        direct=True,
                        constraint=constraint,
                        pinned=is_constraint_pinned(constraint),
                    )
                )
            for name, constraint in direct_dev_deps.items():
                ver = constraint.lstrip("^~>=")
                purl = make_purl("npm", name, ver)
                self.components.append(
                    Component(
                        name=name,
                        version=ver,
                        ecosystem="npm",
                        purl=purl,
                        surface="apps/web",
                        scope="optional",
                        direct=True,
                        constraint=constraint,
                        pinned=is_constraint_pinned(constraint),
                    )
                )
            return

        with open(lock_path, encoding="utf-8") as f:
            lock_data = json.load(f)

        packages = lock_data.get("packages", {})
        # npm lockfile v3 format: entries like "node_modules/@tanstack/react-virtual"
        for pkg_key, pkg_info in packages.items():
            if not pkg_key:
                continue  # root package entry
            # Extract standard package name from "node_modules/..."
            if pkg_key.startswith("node_modules/"):
                name = pkg_key[len("node_modules/"):]
                # handle nested node_modules
                if "node_modules/" in name:
                    name = name.split("node_modules/")[-1]
            else:
                name = pkg_key

            version = pkg_info.get("version", "")
            if not version:
                continue

            is_dev = pkg_info.get("dev", False)
            scope = "optional" if is_dev else "required"

            is_direct = False
            constraint = ""
            if name in direct_deps:
                is_direct = True
                constraint = direct_deps[name]
                scope = "required"
            elif name in direct_dev_deps:
                is_direct = True
                constraint = direct_dev_deps[name]
                scope = "optional"

            integrity = pkg_info.get("integrity", "")
            hash_val = ""
            hash_alg = ""
            if integrity and "-" in integrity:
                alg, h = integrity.split("-", 1)
                hash_val = h
                hash_alg = "SHA-512" if alg.lower() == "sha512" else alg.upper()

            purl = make_purl("npm", name, version)
            dep_names = list(pkg_info.get("dependencies", {}).keys())

            comp = Component(
                name=name,
                version=version,
                ecosystem="npm",
                purl=purl,
                surface="apps/web",
                scope=scope,
                direct=is_direct,
                constraint=constraint,
                pinned=is_constraint_pinned(constraint) if is_direct else True,
                integrity_hash=hash_val,
                hash_algorithm=hash_alg,
                license=pkg_info.get("license", ""),
                dependencies=dep_names,
            )
            self.components.append(comp)

    def scan_flutter_mobile(self) -> None:
        pubspec_path = self.repo_root / "apps/mobile" / "pubspec.yaml"
        lock_path = self.repo_root / "apps/mobile" / "pubspec.lock"

        if not pubspec_path.is_file():
            return

        pub_text = pubspec_path.read_text(encoding="utf-8")
        if yaml is not None:
            pub_data = yaml.safe_load(pub_text) or {}
        else:
            pub_data = _parse_yaml_fallback(pub_text)

        direct_deps = pub_data.get("dependencies", {})
        direct_dev_deps = pub_data.get("dev_dependencies", {})

        if not lock_path.is_file():
            self.missing_lockfiles.append("apps/mobile/pubspec.lock")
            return

        lock_text = lock_path.read_text(encoding="utf-8")
        if yaml is not None:
            lock_data = yaml.safe_load(lock_text) or {}
        else:
            lock_data = _parse_yaml_fallback(lock_text)

        packages = lock_data.get("packages", {})
        for name, info in packages.items():
            version = str(info.get("version", ""))
            dep_type = str(info.get("dependency", ""))
            desc = info.get("description", {})
            sha256 = ""
            if isinstance(desc, dict):
                sha256 = desc.get("sha256", "")

            is_direct = "direct" in dep_type
            is_dev = "dev" in dep_type
            scope = "optional" if is_dev else "required"

            constraint = ""
            if name in direct_deps:
                raw_c = direct_deps[name]
                constraint = raw_c if isinstance(raw_c, str) else str(raw_c)
            elif name in direct_dev_deps:
                raw_c = direct_dev_deps[name]
                constraint = raw_c if isinstance(raw_c, str) else str(raw_c)

            purl = make_purl("pub", name, version)
            comp = Component(
                name=name,
                version=version,
                ecosystem="pub",
                purl=purl,
                surface="apps/mobile",
                scope=scope,
                direct=is_direct,
                constraint=constraint,
                pinned=is_constraint_pinned(constraint) if is_direct else True,
                integrity_hash=sha256,
                hash_algorithm="SHA-256" if sha256 else "",
            )
            self.components.append(comp)

    def to_cyclonedx(self) -> dict[str, Any]:
        now = datetime.datetime.now(datetime.UTC).isoformat()
        bom_uuid = str(uuid.uuid4())

        components_json = [c.to_cyclonedx() for c in self.components]

        # CycloneDX dependency list
        deps_list: list[dict[str, Any]] = []
        for purl, dep_purls in self.dependencies_graph.items():
            deps_list.append({
                "ref": purl,
                "dependsOn": dep_purls,
            })

        return {
            "$schema": "http://cyclonedx.org/schema/bom-1.5.json",
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "serialNumber": f"urn:uuid:{bom_uuid}",
            "version": 1,
            "metadata": {
                "timestamp": now,
                "tools": [
                    {
                        "vendor": "CLARA-Care",
                        "name": "clara-sbom-generator",
                        "version": "1.0.0",
                    }
                ],
                "component": {
                    "bom-ref": "pkg:generic/clara-platform@0.1.0",
                    "type": "application",
                    "name": "CLARA-Care",
                    "version": "0.1.0",
                    "description": "Vietnamese Medical AI Assistant Platform",
                },
            },
            "components": components_json,
            "dependencies": deps_list,
        }

    def to_manifest(self) -> dict[str, Any]:
        now = datetime.datetime.now(datetime.UTC).isoformat()
        total = len(self.components)
        pypi_count = sum(1 for c in self.components if c.ecosystem == "pypi")
        npm_count = sum(1 for c in self.components if c.ecosystem == "npm")
        pub_count = sum(1 for c in self.components if c.ecosystem == "pub")

        direct_components = [c for c in self.components if c.direct]
        unpinned_direct = [c for c in direct_components if not c.pinned]

        # Lockfile hashes
        lockfile_checksums: dict[str, str] = {}
        for lock_rel in ("services/api/uv.lock", "services/ml/uv.lock", "apps/web/package-lock.json", "apps/mobile/pubspec.lock"):
            lp = self.repo_root / lock_rel
            if lp.is_file():
                h = hashlib.sha256(lp.read_bytes()).hexdigest()
                lockfile_checksums[lock_rel] = h

        return {
            "schema_version": "1.0.0",
            "generated_at": now,
            "repo_root": str(self.repo_root),
            "summary": {
                "total_components": total,
                "ecosystems": {
                    "pypi": pypi_count,
                    "npm": npm_count,
                    "pub": pub_count,
                },
                "direct_dependencies_count": len(direct_components),
                "unpinned_direct_count": len(unpinned_direct),
                "pinned_direct_count": len(direct_components) - len(unpinned_direct),
                "missing_lockfiles": self.missing_lockfiles,
            },
            "lockfile_checksums": lockfile_checksums,
            "unpinned_direct_dependencies": [
                {
                    "name": c.name,
                    "surface": c.surface,
                    "ecosystem": c.ecosystem,
                    "scope": c.scope,
                    "declared_constraint": c.constraint,
                    "resolved_version": c.version,
                }
                for c in unpinned_direct
            ],
            "components": [asdict(c) for c in self.components],
        }

    def print_summary(self) -> None:
        manifest = self.to_manifest()
        s = manifest["summary"]
        print("=" * 70)
        print("CLARA SUPPLY-CHAIN SBOM SUMMARY")
        print("=" * 70)
        print(f"Total Components Identified: {s['total_components']}")
        print(f"  • Python (pypi):           {s['ecosystems']['pypi']}")
        print(f"  • Node.js (npm):           {s['ecosystems']['npm']}")
        print(f"  • Flutter / Dart (pub):    {s['ecosystems']['pub']}")
        print("-" * 70)
        print(f"Direct Dependencies:         {s['direct_dependencies_count']}")
        print(f"  • Pinned exact:            {s['pinned_direct_count']}")
        print(f"  • Unpinned / range:        {s['unpinned_direct_count']}")
        if s["missing_lockfiles"]:
            print("-" * 70)
            print("[WARN] Surfaces lacking hermetic lockfiles:")
            for m in s["missing_lockfiles"]:
                print(f"  - {m}")
        print("=" * 70)


def generate_sbom(
    repo_root: Path,
    output_dir: Path | None = None,
    format_type: str = "both",
    cyclonedx_out: Path | None = None,
    manifest_out: Path | None = None,
    summary: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    builder = SbomBuilder(repo_root)
    builder.scan_all()

    cyclonedx_data = builder.to_cyclonedx()
    manifest_data = builder.to_manifest()

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        if format_type in ("cyclonedx", "both"):
            target = cyclonedx_out or (output_dir / "sbom.cyclonedx.json")
            target.write_text(json.dumps(cyclonedx_data, indent=2), encoding="utf-8")
            print(f"[SBOM] Wrote CycloneDX SBOM to {target}")
        if format_type in ("manifest", "both"):
            target = manifest_out or (output_dir / "sbom_manifest.json")
            target.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
            print(f"[SBOM] Wrote CLARA Supply Chain Manifest to {target}")

    if summary:
        builder.print_summary()

    return cyclonedx_data, manifest_data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        default=str(Path.cwd()),
        help="Path to repository root",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to write output SBOM and manifest files",
    )
    parser.add_argument(
        "--format",
        choices=["cyclonedx", "manifest", "both"],
        default="both",
        help="Output format to generate (default: both)",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print summary table to stdout",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root)
    output_dir = Path(args.output_dir) if args.output_dir else None

    generate_sbom(
        repo_root=repo_root,
        output_dir=output_dir,
        format_type=args.format,
        summary=args.summary,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
