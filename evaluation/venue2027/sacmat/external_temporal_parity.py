"""Replay public OpenFGA temporal-access assertions on native OpenFGA and OPA.

Run as a module with the pinned store.fga.yaml path (see SOURCE). Requires
Docker with IMAGE, fga CLI v0.9.0, and OPA v1.22.4. The memory-backed server
is disposable and binds only to an ephemeral loopback port. No provider calls.
Published assertions and additional exact-expiry controls are separate strata.
"""

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

import yaml

from evaluation.venue2027.sacmat.openfga_adapter import OpenFgaEngineError, _http_json

SOURCE = "https://raw.githubusercontent.com/openfga/sample-stores/6802b4d859d2773eea72c2315b3a9f027a2893a0/stores/temporal-access/store.fga.yaml"
SOURCE_HASH = "60d3fb4076a1c374713ca10de32c6596bc2dc33cab978e37a9eef75b79b13bfb"
IMAGE = "openfga/openfga@sha256:b852071314f1fda1194d341a6ebac0a4f619b3cd87a6626d2ccc7048af4ec671"
POLICY = Path(__file__).with_name("fixtures") / "temporal_access.rego"


def checked(*args, **options):
    return subprocess.check_output(args, text=True, timeout=30, **options).strip()


@contextmanager
def server():
    cid = checked(
        "docker",
        "run",
        "--pull=never",
        "--rm",
        "-d",
        "-p",
        "127.0.0.1::8080",
        IMAGE,
        "run",
        "--datastore-engine=memory",
        "--playground-enabled=false",
    )
    try:
        port = checked("docker", "port", cid, "8080/tcp")
        if not port.startswith("127.0.0.1:") or not port.split(":")[1].isdigit():
            raise RuntimeError("private_port_required")
        url = "http://" + port
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(url + "/healthz", timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            raise TimeoutError("openfga_startup")
        yield url
    finally:
        checked("docker", "stop", cid)


def cases(store):
    for test in store["tests"]:
        for kind, queries in test.items():
            if kind == "name":
                continue
            if kind not in {"check", "list_objects", "list_users"}:
                raise ValueError("unsupported_source_query")
            for query in queries:
                for relation, expected in query["assertions"].items():
                    if kind == "list_users":
                        expected = expected["users"]
                    yield (
                        "published",
                        kind,
                        {k: v for k, v in query.items() if k != "assertions"}
                        | {"relation": relation},
                        expected,
                    )
    # One nanosecond before, exactly at, and one nanosecond after both deadlines.
    for obj, times in [
        ("document:1", ("00:59:59.999999999", "01:00:00", "01:00:00.000000001")),
        ("document:2", ("00:00:04.999999999", "00:00:05", "00:00:05.000000001")),
    ]:
        for stamp, allowed in zip(times, (True, False, False), strict=True):
            yield (
                "expiry_boundary_dev",
                "check",
                {
                    "user": "user:anne",
                    "object": obj,
                    "relation": "viewer",
                    "context": {"current_time": f"2023-01-01T{stamp}Z"},
                },
                allowed,
            )


def fga_query(post, path, model, kind, query):
    payload = {"authorization_model_id": model, "consistency": "HIGHER_CONSISTENCY"}
    if kind == "check":
        payload["tuple_key"] = {k: query[k] for k in ("user", "object", "relation")}
        if "context" in query:
            payload["context"] = query["context"]
        return post(path + "/check", payload)["allowed"]
    if kind == "list_objects":
        return sorted(post(path + "/list-objects", payload | query)["objects"])
    obj_type, obj_id = query["object"].split(":", 1)
    payload.update(
        relation=query["relation"],
        object={"type": obj_type, "id": obj_id},
        user_filters=query["user_filter"],
        context=query["context"],
    )
    users = post(path + "/list-users", payload)["users"]
    return sorted(x["object"]["type"] + ":" + x["object"]["id"] for x in users)


def replay(source_path):
    raw = source_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_HASH:
        raise ValueError("external_store_digest_mismatch")
    store = yaml.safe_load(raw)
    engine = checked("opa", "version").splitlines()[0].removeprefix("Version: ").strip()
    fga_version = checked("fga", "version")
    if engine != "1.22.4" or not fga_version.startswith("fga version v`0.9.0` "):
        raise ValueError("unexpected_cli_version")
    rows = []
    with tempfile.TemporaryDirectory() as tmp, server() as url:
        folder = Path(tmp)
        model_file = folder / "source.fga"
        model_file.write_text(store["model"])
        model = json.loads(
            checked(
                "fga", "model", "transform", "--file", str(model_file), "--output-format", "json"
            )
        )

        def post(path, payload):
            return _http_json("POST", url + path, payload, "", 10)

        path = "/stores/" + post("/stores", {"name": "temporal-parity"})["id"]
        mid = post(path + "/authorization-models", model)["authorization_model_id"]
        post(
            path + "/write",
            {"authorization_model_id": mid, "writes": {"tuple_keys": store["tuples"]}},
        )
        data = folder / "data.json"
        data.write_text(json.dumps({"tuples": store["tuples"]}))
        for group, kind, query, expected in cases(store):
            row = dict(
                group=group,
                operation=kind,
                query=query,
                expected=sorted(expected) if isinstance(expected, list) else expected,
            )
            try:
                row["openfga"] = fga_query(post, path, mid, kind, query)
            except (OpenFgaEngineError, ValueError, KeyError, OSError) as exc:
                row["openfga_error"] = type(exc).__name__
            try:
                response = json.loads(
                    checked(
                        "opa",
                        "eval",
                        "--format=json",
                        "--stdin-input",
                        "-d",
                        str(POLICY),
                        "-d",
                        str(data),
                        "data.temporal_access." + kind,
                        input=json.dumps(query),
                    )
                )
                value = response["result"][0]["expressions"][0]["value"]
                row["opa"] = sorted(value) if isinstance(value, list) else value
            except (ValueError, KeyError, IndexError, subprocess.SubprocessError) as exc:
                row["opa_error"] = type(exc).__name__
            rows.append(row)
    summary = {}
    for group in ("published", "expiry_boundary_dev"):
        summary[group] = {}
        for arm in ("opa", "openfga"):
            counts = Counter()
            for row in rows:
                if row["group"] != group:
                    continue
                if arm not in row:
                    counts["error"] += 1
                elif row[arm] == row["expected"]:
                    counts["match"] += 1
                else:
                    counts["disagree"] += 1
            summary[group][arm] = dict(counts)
    return dict(
        source=SOURCE,
        source_sha256=SOURCE_HASH,
        openfga_image=IMAGE,
        opa=engine,
        opa_binary_sha256=hashlib.sha256(Path(shutil.which("opa")).read_bytes()).hexdigest(),
        fga_cli=fga_version,
        translation_sha256=hashlib.sha256(POLICY.read_bytes()).hexdigest(),
        summary=summary,
        rows=rows,
    )


if __name__ == "__main__":
    print(json.dumps(replay(Path(sys.argv[1])), indent=2))
