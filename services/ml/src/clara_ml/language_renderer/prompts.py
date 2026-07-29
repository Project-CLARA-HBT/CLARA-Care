"""Versioned contract marker for a future generative renderer.

The current production path is deterministic.  A generative implementation
must preserve this contract and pass the same verifier before it can ship.
"""

PROMPT_VERSION = "language-renderer-contract-v1"
