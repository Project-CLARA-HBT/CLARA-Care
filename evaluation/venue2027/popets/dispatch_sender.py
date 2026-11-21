"""Local synthetic sender v1. stdout carries data frames, stderr carries cancellation IDs.

Invoked only with B2 or B4. Exceptions or timeouts invalidate the entire paired run.
The fixed fixture represents derived projections as identity copies of one source field.
"""

import argparse
import os
import sys

from evaluation.venue2027.popets.candidate import CacheEntry, RevocationCompleteCache
from evaluation.venue2027.popets.dispatch_fixture import History, Request, schedule


def recompute(history: History, request: Request) -> str | None:
    # Resolve the requested projection against the current source grant on every call.
    source = history.sources[request.source]
    if request.purpose != source.purpose or source.visit > request.time:
        return None
    if source.retired is not None and request.time >= source.retired:
        return None
    return source.value


class WarmCache:
    def __init__(self, history: History):
        self.history = history
        self.cache = RevocationCompleteCache()
        self.pending = sorted(
            {(s.retired, s.purpose) for s in history.sources if s.retired is not None}
        )
        self.loaded = 0
        self.entries: dict[str, CacheEntry] = {}

    def read(self, request: Request) -> str | None:
        while self.loaded < len(self.history.sources):
            idx = self.loaded
            source = self.history.sources[idx]
            if source.visit > request.time:
                break
            parent: tuple[str, ...] = ()
            for path in ("prompt", "summary", "retry", "fallback"):
                key = f"{idx}/{path}"
                # Queued copies carry a local routing label. Their source authority
                # is represented by the parent edge, which revocation must traverse.
                origin = self.history.subject if not parent else "synthetic-queue"
                entry = self.cache.put(
                    key,
                    source.value,
                    [(origin, source.purpose, 0)],
                    derived_from=parent,
                )
                self.entries[key] = entry
                parent = (key,)
            self.loaded += 1
        while self.pending and self.pending[0][0] <= request.time:
            _, purpose = self.pending.pop(0)
            self.cache.revoke(self.history.subject, purpose, 0)
        path = "summary" if request.path == "retained" else request.path
        key = f"{request.source}/{path}"
        if self.cache.get(key, request.purpose, 0).status == "HIT":
            return self.entries[key].value
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arm", choices=("B2", "B4"))
    arm = parser.parse_args().arm
    for history in schedule()[0]:
        cache = WarmCache(history) if arm == "B4" else None
        for request in history.requests:
            if sys.stdin.buffer.readline() != request.id.encode() + b"\n":
                raise ValueError("SCHEDULE_COMMAND_MISMATCH")
            value = cache.read(request) if cache else recompute(history, request)
            if value is None:
                os.write(2, request.id.encode() + b"\n")
            else:
                os.write(1, request.id.encode() + b"\t" + value.encode() + b"\n")

    if sys.stdin.buffer.read(1):
        raise ValueError("EXTRA_COMMAND")


if __name__ == "__main__":
    main()
