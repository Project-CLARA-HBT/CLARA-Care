"""Property-based tests for degraded-mode fail-loud embedding (production).

Feature: rag-knowledge-pipeline, Property 9: Degraded-mode fail-loud (production).

Design reference (design.md -> Correctness Properties):
    Property 9: Degraded-mode fail-loud (production). For any embedding-API
    failure with ``environment='production'``, the client raises
    ``EmbeddingUnavailableError`` and never returns a 16-dim hash or sentinel
    vector.

Requirement 2.1 (requirements.md -> Requirement 2, Acceptance Criteria #1):
    IF the embedding API fails WHILE ``environment`` is ``production``, THEN THE
    Embedding_Client SHALL raise ``EmbeddingUnavailableError``.

Requirement 2.2 (requirements.md -> Requirement 2, Acceptance Criteria #2):
    WHILE ``environment`` is ``production``, THE Embedding_Client SHALL produce
    only model-dimensioned vectors and SHALL NOT return a 16-dimension SHA-256
    hash vector or any sentinel vector on any code path.

Target: :class:`clara_ml.rag.embedder.HttpEmbeddingClient` and
:class:`clara_ml.rag.embedder.EmbeddingUnavailableError`.

Strategy: the canonical fail-loud surface (``embed_documents`` / ``embed_query``)
is exercised across a wide band of *production-like* configurations and a
stubbed/injected failing transport. A configuration is "production-like" (i.e.
fail-loud is mandatory) when EITHER:

  * ``environment`` normalizes to ``production`` (any ``RAG_EMBEDDING_ALLOW_DEGRADED``
    value), OR
  * ``environment`` is non-production AND ``RAG_EMBEDDING_ALLOW_DEGRADED`` is false.

For every such configuration and every injected transport failure (network /
timeout / payload / dimension errors, plus the no-API-key-configured failure
mode), the client MUST raise ``EmbeddingUnavailableError`` and MUST NOT return a
silent fallback vector. A complementary property asserts the degraded sentinel
path activates ONLY in the non-production + allow-degraded configuration.

Validates: Requirements 2.1, 2.2.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
from unittest import mock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Import the store package first: ``clara_ml.rag.store`` eagerly pulls in
# ``hybrid_retriever`` -> ``score_engine`` -> ``HttpEmbeddingClient``; importing
# it before the embedder avoids a partially-initialized-module import cycle.
import clara_ml.rag.store  # noqa: F401  (import-order guard for the known circular-import quirk)
import clara_ml.rag.embedder as embedder_mod
from clara_ml.rag.embedder import EmbeddingUnavailableError, HttpEmbeddingClient

# --- configuration strategies ------------------------------------------------

# Environments that normalize (strip + lower) to "production". Includes a
# surrounding-whitespace / mixed-case variant to exercise the normalization in
# ``HttpEmbeddingClient._is_production``.
_prod_environments = st.sampled_from(
    ["production", "PRODUCTION", "Production", " production "]
)

# Non-production environment labels.
_nonprod_environments = st.sampled_from(
    ["development", "dev", "test", "staging", "local", ""]
)

# Production-like configs where fail-loud is MANDATORY for the canonical
# (non-lenient) ``embed_documents`` / ``embed_query`` surface:
#   * production + any allow_degraded value, OR
#   * non-production + allow_degraded disabled.
_fail_loud_config = st.one_of(
    st.tuples(_prod_environments, st.booleans()),
    st.tuples(_nonprod_environments, st.just(False)),
)

# The single configuration where the explicit degraded sentinel path is allowed
# to activate instead of failing loud: non-production AND allow-degraded enabled.
_degraded_config = st.tuples(_nonprod_environments, st.just(True))

# Injected transport failures: network, timeout, malformed-payload, dimension,
# and generic provider errors. Each is a concrete exception raised by the stub
# in place of a live embedding call.
_transport_errors = st.sampled_from(
    [
        ConnectionError("connection refused"),
        TimeoutError("request timed out"),
        OSError("network is unreachable"),
        ValueError("Embedding response missing data"),
        ValueError("Embedding response size mismatch"),
        RuntimeError("provider returned HTTP 500"),
    ]
)

# Input texts: ascii, Vietnamese/unicode, and whitespace-variant strings.
_text = st.one_of(
    st.text(max_size=48),
    st.sampled_from(
        [
            "paracetamol và ibuprofen",
            "tương tác thuốc nghiêm trọng",
            "liều dùng cho trẻ em",
            "   ",
            "\tdòng\nmới",
        ]
    ),
)
_doc_texts = st.lists(_text, min_size=1, max_size=5)

_TEST_DIM = 8


@contextmanager
def _force_settings(environment: str, allow_degraded: bool, dim: int = _TEST_DIM) -> Iterator[None]:
    """Temporarily override the embedder's environment / degraded / dim settings.

    Patching is done inside the test body (not via a function-scoped fixture) so
    every Hypothesis example sets up and tears down its own configuration.
    """

    with (
        mock.patch.object(embedder_mod.settings, "environment", environment),
        mock.patch.object(embedder_mod.settings, "rag_embedding_allow_degraded", allow_degraded),
        mock.patch.object(embedder_mod.settings, "rag_embedding_dim", dim),
    ):
        yield


def _client() -> HttpEmbeddingClient:
    """An embedding client with an API key set (so the transport is reached)."""

    return HttpEmbeddingClient(api_key="test-key", base_url="https://example.invalid/v1", model="m")


# --- properties --------------------------------------------------------------


# Feature: rag-knowledge-pipeline, Property 9: Degraded-mode fail-loud (production)
# Validates: Requirements 2.1, 2.2
@settings(max_examples=200, deadline=None)
@given(config=_fail_loud_config, texts=_doc_texts, exc=_transport_errors)
def test_property9_embed_documents_raises_on_api_failure(
    config: tuple[str, bool], texts: list[str], exc: Exception
) -> None:
    """OFFLINE path: a failing transport raises instead of returning a fallback."""

    environment, allow_degraded = config
    client = _client()
    with _force_settings(environment, allow_degraded):
        with mock.patch.object(client, "_request_remote_embeddings", side_effect=exc):
            # MUST raise: never returns a 16-dim hash or sentinel vector.
            with pytest.raises(EmbeddingUnavailableError):
                client.embed_documents(texts)


# Feature: rag-knowledge-pipeline, Property 9: Degraded-mode fail-loud (production)
# Validates: Requirements 2.1, 2.2
@settings(max_examples=200, deadline=None)
@given(config=_fail_loud_config, text=_text, exc=_transport_errors)
def test_property9_embed_query_raises_on_api_failure(
    config: tuple[str, bool], text: str, exc: Exception
) -> None:
    """ONLINE path: a failing transport raises instead of returning a fallback."""

    environment, allow_degraded = config
    client = _client()
    with _force_settings(environment, allow_degraded):
        with mock.patch.object(client, "_request_remote_embeddings", side_effect=exc):
            with pytest.raises(EmbeddingUnavailableError):
                client.embed_query(text)


# Feature: rag-knowledge-pipeline, Property 9: Degraded-mode fail-loud (production)
# Validates: Requirements 2.1, 2.2
@settings(max_examples=150, deadline=None)
@given(config=_fail_loud_config, texts=_doc_texts)
def test_property9_no_api_key_raises(config: tuple[str, bool], texts: list[str]) -> None:
    """An unconfigured API key is a fail-loud failure mode under production-like config."""

    environment, allow_degraded = config
    # No API key configured: the client cannot produce real embeddings.
    client = HttpEmbeddingClient(api_key="", base_url="https://example.invalid/v1", model="m")
    with _force_settings(environment, allow_degraded):
        with pytest.raises(EmbeddingUnavailableError):
            client.embed_documents(texts)
        with pytest.raises(EmbeddingUnavailableError):
            client.embed_query("paracetamol")


# Feature: rag-knowledge-pipeline, Property 9: Degraded-mode fail-loud (production)
# Validates: Requirements 2.1, 2.2
@settings(max_examples=150, deadline=None)
@given(config=_degraded_config, texts=_doc_texts, exc=_transport_errors)
def test_property9_degraded_sentinel_only_in_nonprod_allow_degraded(
    config: tuple[str, bool], texts: list[str], exc: Exception
) -> None:
    """Complement: the explicit sentinel path activates ONLY in non-prod + allow-degraded.

    In this single configuration the client does NOT fail loud; it returns
    explicit, model-dimensioned, ``degraded=True`` zero sentinels (never the
    legacy silent hash vector).
    """

    environment, allow_degraded = config  # non-production, allow_degraded=True
    client = _client()
    with _force_settings(environment, allow_degraded, dim=_TEST_DIM):
        with mock.patch.object(client, "_request_remote_embeddings", side_effect=exc):
            result = client.embed_documents(texts)

    # Explicit degraded sentinels: flagged, model-dimensioned, all-zero.
    assert len(result.vectors) == len(texts)
    assert result.degraded == [True] * len(texts)
    assert all(len(vector) == _TEST_DIM for vector in result.vectors)
    assert all(value == 0.0 for vector in result.vectors for value in vector)
