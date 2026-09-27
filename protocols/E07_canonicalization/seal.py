#!/usr/bin/env python3
"""SHA-256 seal generator script for E07 protocol directory.

Proxies execution to evaluation.canonicalization.seal.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evaluation.canonicalization.seal import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
