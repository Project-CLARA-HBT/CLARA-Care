"""Write and query isolated filesystem archives for original GLHS readback and signed CAS."""

import argparse
import hashlib
import json
import shutil
import struct
from datetime import UTC, datetime
from pathlib import Path

from clara_api.db.models import GlhsSnapshotManifest
from clara_api.glhs.canonical_json import (
    CANONICALIZATION_PROFILE,
    canonical_json_bytes,
    consistency_fingerprint,
)
from clara_api.glhs.gateway import (
    SNAPSHOT_PAYLOAD_SCHEMA_VERSION,
    SNAPSHOT_SCHEMA_VERSION,
    GlhsInvariantError,
    _manifest_envelope,
    reconstruct_snapshot_artifact,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

SOURCE = "5ce28a6e656bc88c1da29c983d243d5a81eb37de92698da3864d1cf02894ca24"
STAGES = ("retained", "partial", "expired")


def pack(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def make_manifest(meta, payload):
    row = GlhsSnapshotManifest(**meta, snapshot_payload_json=payload)
    row.expires_at = datetime.fromisoformat(meta["expires_at"])
    return row


def write(source, archive):
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE:
        raise ValueError("source hash mismatch")
    rows = json.loads(raw)
    archive.mkdir()
    (archive / "meta").mkdir()
    key = Ed25519PrivateKey.generate()
    (archive / "meta" / "signed.pub").write_bytes(
        key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    )
    for scope, dialogue in enumerate(rows):
        for arm in ("glhs", "signed"):
            (archive / "meta" / arm / str(scope)).mkdir(parents=True)
            (archive / "content" / arm / str(scope)).mkdir(parents=True)
        for turn, record in enumerate(dialogue["turns"]):
            if record["speaker"] != "USER":
                continue
            name = f"{scope}/{turn}"
            obj = {"frames": record["frames"]}
            body = canonical_json_bytes(obj)
            digest = hashlib.sha256(body).hexdigest()
            meta = dict(
                public_id=name,
                profile_id=scope + 1,
                actor_user_id=None,
                actor_role="researcher",
                state_version=turn,
                policy_version="study",
                consent_version="study",
                purpose="study",
                task="source_readback",
                consent_basis="study",
                expires_at=datetime(2030, 1, 1, tzinfo=UTC).isoformat(),
                valid_time_cutoff=None,
                knowledge_time_cutoff=None,
                data_classes_json=[],
                assertion_ids_json=[],
                assertion_hashes_json=[],
                provenance_ids_json=[],
                conflict_ids_json=[],
                selection_policy="all",
                manifest_schema_version=SNAPSHOT_SCHEMA_VERSION,
                payload_schema_version=SNAPSHOT_PAYLOAD_SCHEMA_VERSION,
                digest_algorithm="sha-256",
                canonicalization_profile=CANONICALIZATION_PROFILE,
                snapshot_digest=consistency_fingerprint(obj),
            )
            meta["manifest_digest"] = consistency_fingerprint(
                _manifest_envelope(make_manifest(meta, obj))
            )
            (archive / "meta" / "glhs" / name).write_bytes(pack(meta))
            (archive / "content" / "glhs" / name).write_bytes(body)
            receipt = dict(scope=scope, turn=turn, sha256=digest)
            signature = key.sign(pack(receipt)).hex()
            (archive / "meta" / "signed" / name).write_bytes(
                pack(dict(receipt=receipt, signature=signature))
            )
            blob = archive / "content" / "signed" / str(scope) / digest
            if not blob.exists():
                blob.write_bytes(body)


def retrieve_glhs(archive, scope, turn):
    name = f"{scope}/{turn}"
    meta = json.loads((archive / "meta" / "glhs" / name).read_bytes())
    if meta["public_id"] != name or meta["profile_id"] != scope + 1:
        raise ValueError("wrong GLHS manifest")
    blob = archive / "content" / "glhs" / name
    payload = json.loads(blob.read_bytes()) if blob.is_file() else None
    try:
        result = reconstruct_snapshot_artifact(make_manifest(meta, payload))
    except GlhsInvariantError as exc:
        if payload is None and str(exc) == "snapshot_payload_unavailable":
            return None
        raise
    return canonical_json_bytes(result["payload"])


def retrieve_signed(archive, scope, turn, key):
    msg = json.loads((archive / "meta" / "signed" / str(scope) / str(turn)).read_bytes())
    r = msg["receipt"]
    key.verify(bytes.fromhex(msg["signature"]), pack(r))
    if (r["scope"], r["turn"]) != (scope, turn):
        raise ValueError("wrong signed receipt")
    path = archive / "content" / "signed" / str(scope) / r["sha256"]
    if not path.is_file():
        return None
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != r["sha256"]:
        raise ValueError("corrupt blob")
    return body


def size(path):
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def read(archive, out):
    out.mkdir()
    key = Ed25519PublicKey.from_public_bytes((archive / "meta" / "signed.pub").read_bytes())
    sizes = []
    for stage in STAGES:
        for arm in ("glhs", "signed"):
            blobs = archive / "content" / arm
            if stage != "retained":
                for directory in blobs.iterdir():
                    if stage == "expired" or int(directory.name) % 3 == 0:
                        shutil.rmtree(directory)
            meta = archive / "meta" / arm
            overhead = size(meta) + (32 if arm == "signed" else 0)
            sizes.append(
                dict(stage=stage, arm=arm, metadata_bytes=overhead, content_bytes=size(blobs))
            )
            with (out / f"{arm}-{stage}.bin").open("xb") as stream:
                for scope, turn in sorted(
                    (int(f.parent.name), int(f.name)) for f in meta.glob("*/*")
                ):
                    body = (
                        retrieve_glhs(archive, scope, turn)
                        if arm == "glhs"
                        else retrieve_signed(archive, scope, turn, key)
                    )
                    stream.write(
                        struct.pack(">III", scope, turn, 0xFFFFFFFF if body is None else len(body))
                    )
                    if body is not None:
                        stream.write(body)
    (out / "sizes.json").write_text(json.dumps(sizes, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "read"))
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    args = parser.parse_args()
    (write if args.action == "write" else read)(args.first, args.second)
