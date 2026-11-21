"""Independent v1 receiver/reducer for the closed synthetic single-attribute IPC protocol.

Inputs are the replayed development schedule and two receiver-side byte streams. Any
unknown bytes, malformed frames, duplicate, missing, or conflicting delivery fail the
run. A cancellation cannot erase an observed delivery. No arm decisions enter the oracle.
"""

from collections import Counter
from hashlib import sha256
from typing import Any

from evaluation.venue2027.popets.dispatch_fixture import History


def _frames(raw: bytes) -> list[bytes]:
    if raw and not raw.endswith(b"\n"):
        raise ValueError("TRUNCATED_FRAME")
    return raw.split(b"\n")[:-1]


def reconcile(histories: list[History], data: bytes, cancellations: bytes) -> tuple[list, dict]:
    delivered = {}
    for frame in _frames(data):
        key, sep, value = frame.partition(b"\t")
        if not sep or not value or key in delivered:
            raise ValueError("INVALID_DELIVERY")
        delivered[key] = value
    cancelled = _frames(cancellations)
    pending = set(cancelled)
    planned = [r.id.encode() for h in histories for r in h.requests]
    if (
        len(cancelled) != len(pending)
        or pending.intersection(delivered)
        or pending.union(delivered) != set(planned)
        or list(delivered) != [key for key in planned if key in delivered]
        or cancelled != [key for key in planned if key in pending]
        or len(planned) != len(set(planned))
    ):
        raise ValueError("UNRECONCILED_SCHEDULE")

    alphabet = {s.value.encode() for h in histories for s in h.sources}
    if len(alphabet) != sum(len(h.sources) for h in histories) or any(
        len(v) != 32 for v in alphabet
    ):
        raise ValueError("INVALID_SOURCE_CODEBOOK")
    rows: list[dict[str, Any]] = []
    eligible = set()
    leaking = set()
    paths: Counter[str] = Counter()
    for history in histories:
        barriers = [s.retired for s in history.sources if s.retired is not None]
        for request in history.requests:
            # Fixture recipe names exactly one origin. Replay grants at logical send time.
            authorized = {
                s.value.encode()
                for i, s in enumerate(history.sources)
                if i == request.source
                and s.visit <= request.time
                and s.purpose == request.purpose
                and (s.retired is None or request.time < s.retired)
            }
            observed = delivered.get(request.id.encode(), b"")
            chunks = [observed[i : i + 32] for i in range(0, len(observed), 32)]
            if any(chunk not in alphabet for chunk in chunks):
                raise ValueError("UNCLASSIFIABLE_BYTES")
            forbidden = sum(len(chunk) for chunk in chunks if chunk not in authorized)
            post = bool(barriers and request.time >= min(barriers))
            if post:
                eligible.add(history.subject)
                if forbidden:
                    leaking.add(history.subject)
            paths[request.path] += 1
            rows.append(
                dict(
                    subject=history.subject,
                    family=history.family,
                    tenant=history.tenant,
                    request=request.id,
                    path=request.path,
                    post_revocation=post,
                    cancelled=request.id.encode() in pending,
                    received_bytes=len(observed),
                    payload_sha256=sha256(observed).hexdigest(),
                    forbidden_bytes=forbidden,
                    authorized_bytes_requested=32 * len(authorized),
                    authorized_bytes_delivered=32 * len(authorized.intersection(chunks)),
                    exact_projection=observed == b"".join(authorized),
                )
            )
    requested = sum(r["authorized_bytes_requested"] for r in rows)
    retained = sum(r["authorized_bytes_delivered"] for r in rows)
    post_rows = [r for r in rows if r["post_revocation"]]
    return rows, dict(
        post_revocation_scheduled=len(post_rows),
        post_revocation_cancelled=sum(r["cancelled"] for r in post_rows),
        post_revocation_authorized_bytes_requested=sum(
            r["authorized_bytes_requested"] for r in post_rows
        ),
        post_revocation_authorized_bytes_delivered=sum(
            r["authorized_bytes_delivered"] for r in post_rows
        ),
        scheduled=len(planned),
        received=len(delivered),
        cancelled=len(cancelled),
        reconciled_by_path=dict(paths),
        post_revocation_subjects=len(eligible),
        leaking_post_revocation_subjects=len(leaking),
        post_revocation_disclosure_rate=len(leaking) / len(eligible) if eligible else None,
        post_revocation_forbidden_bytes=sum(
            r["forbidden_bytes"] for r in rows if r["post_revocation"]
        ),
        all_forbidden_bytes=sum(r["forbidden_bytes"] for r in rows),
        requested_authorized_bytes=requested,
        delivered_authorized_bytes=retained,
        authorized_coverage=retained / requested if requested else None,
        exact_projections=sum(r["exact_projection"] for r in rows),
    )
