"""Property-based tests for embedding determinism in the persistent cache.

Feature: rag-knowledge-pipeline, Property 8: Embedding determinism (cache).

Design reference (design.md → Correctness Properties):
    Property 8: Embedding determinism (cache). For any text embedded twice with
    the same ``model_id``, the cached vector returned is byte-identical on the
    second read.

Requirement 12.1 (requirements.md → Requirement 12, Acceptance Criteria #1):
    WHEN a text is embedded twice under the same ``model_id``, THE Cache_Layer
    SHALL return a byte-identical vector on the second read.

Target: :class:`clara_ml.rag.store.cache.EmbeddingCache` (and, optionally, its
durable :class:`clara_ml.rag.store.cache.JsonFileCacheBackend`).

Byte-identity is asserted with ``struct.pack('<d', x)`` over every element so
the test is sensitive to *bit-level* differences (including ``-0.0`` vs ``0.0``
and distinct NaN payloads), which a naive ``==`` list comparison would miss. We
generate random ``model_id`` strings, texts (ASCII, Vietnamese/unicode, and
whitespace-variant strings), and finite float vectors, and assert:

* repeated ``get`` after a single ``put`` is byte-identical across reads;
* a second ``put`` of the *same* ``(model_id, text)`` followed by ``get`` is
  still byte-identical to the stored vector;
* ``model_id`` isolation — a different ``model_id`` is a cache miss (``None``);
* the durable :class:`JsonFileCacheBackend` round-trips byte-identically after
  the cache is rebuilt from the same file (process-restart simulation).

Validates: Requirements 12.1.
"""

from __future__ import annotations

import struct

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.rag.store.cache import (
    EmbeddingCache,
    JsonFileCacheBackend,
)

# --- generators --------------------------------------------------------------

# model_id surfaces: realistic provider/model labels plus adversarial empties
# and whitespace so the (model_id, text) key composition is exercised broadly.
_model_ids = st.one_of(
    st.sampled_from(
        [
            "text-embedding-3-large",
            "bge-m3",
            "text-embedding-3-small",
            "",
            "  ",
            "model\x1fwith-sep",
        ]
    ),
    st.text(max_size=24),
)

# Vietnamese / unicode fragments to force multi-byte text through the key path.
_vietnamese = st.sampled_from(
    [
        "paracetamol và ibuprofen",
        "Thuốc kháng sinh",
        "liều dùng cho trẻ em",
        "tương tác thuốc nghiêm trọng",
        "Đường huyết cao",
        "café \u00e9\u00e8\u00ea",
        "  khoảng  trắng  thừa  ",
        "\ttab\nnewline\r\n",
    ]
)

_texts = st.one_of(
    st.text(max_size=64),
    _vietnamese,
    # whitespace-variant strings: leading/trailing/internal runs of spaces so
    # the normalization in the cache key is exercised, including all-whitespace.
    st.builds(
        lambda core, lead, trail: f"{' ' * lead}{core}{' ' * trail}",
        st.text(max_size=32),
        st.integers(min_value=0, max_value=4),
        st.integers(min_value=0, max_value=4),
    ),
)

# Finite floats only (no NaN/inf): the JSON durable backend relies on JSON which
# cannot represent NaN/inf, and the in-memory contract is byte-identity over
# finite doubles. Subnormals and signed zero are intentionally allowed.
_floats = st.floats(allow_nan=False, allow_infinity=False, width=64)

_vectors = st.lists(_floats, min_size=1, max_size=16)


def _packed(vector: list[float]) -> bytes:
    """Pack a vector to its little-endian IEEE-754 double byte representation."""

    return struct.pack(f"<{len(vector)}d", *vector)


# --- properties --------------------------------------------------------------


# Feature: rag-knowledge-pipeline, Property 8: Embedding determinism (cache)
# Validates: Requirements 12.1
@settings(max_examples=200, deadline=None)
@given(model_id=_model_ids, text=_texts, vector=_vectors)
def test_property8_repeated_get_is_byte_identical(
    model_id: str, text: str, vector: list[float]
) -> None:
    """After put, every get returns a byte-identical vector."""

    cache = EmbeddingCache()
    cache.put(model_id, text, vector)

    expected = _packed([float(v) for v in vector])

    first = cache.get(model_id, text)
    assert first is not None
    assert _packed(first) == expected

    # Repeated reads must be byte-identical to the first read (and each other).
    for _ in range(3):
        again = cache.get(model_id, text)
        assert again is not None
        assert _packed(again) == expected


# Feature: rag-knowledge-pipeline, Property 8: Embedding determinism (cache)
# Validates: Requirements 12.1
@settings(max_examples=200, deadline=None)
@given(model_id=_model_ids, text=_texts, vector=_vectors)
def test_property8_reput_then_get_is_still_identical(
    model_id: str, text: str, vector: list[float]
) -> None:
    """A second put of the same (model_id, text) leaves get byte-identical."""

    cache = EmbeddingCache()
    cache.put(model_id, text, vector)
    # Re-put the same value; the re-read must still match bit-for-bit.
    cache.put(model_id, text, vector)

    expected = _packed([float(v) for v in vector])
    after_reput = cache.get(model_id, text)
    assert after_reput is not None
    assert _packed(after_reput) == expected

    # A second read after the re-put is identical to the first.
    second = cache.get(model_id, text)
    assert second is not None
    assert _packed(second) == _packed(after_reput)


# Feature: rag-knowledge-pipeline, Property 8: Embedding determinism (cache)
# Validates: Requirements 12.1
@settings(max_examples=200, deadline=None)
@given(
    model_a=st.text(max_size=16),
    model_b=st.text(max_size=16),
    text=_texts,
    vector=_vectors,
)
def test_property8_model_id_isolation(
    model_a: str, model_b: str, text: str, vector: list[float]
) -> None:
    """A different model_id is a cache miss for the same text.

    Keys are composed from the *normalized* model_id (``str.strip()``), so two
    model ids are isolated iff they differ after stripping. When they collide
    under normalization the lookup is expected to hit (and be identical).
    """

    cache = EmbeddingCache()
    cache.put(model_a, text, vector)

    expected = _packed([float(v) for v in vector])
    if model_a.strip() == model_b.strip():
        hit = cache.get(model_b, text)
        assert hit is not None
        assert _packed(hit) == expected
    else:
        assert cache.get(model_b, text) is None
        # The original model_id still resolves and is byte-identical.
        original = cache.get(model_a, text)
        assert original is not None
        assert _packed(original) == expected


# Feature: rag-knowledge-pipeline, Property 8: Embedding determinism (cache)
# Validates: Requirements 12.1
@settings(max_examples=100, deadline=None)
@given(model_id=_model_ids, text=_texts, vector=_vectors)
def test_property8_json_backend_round_trip_is_byte_identical(
    model_id: str,
    text: str,
    vector: list[float],
    tmp_path_factory,
) -> None:
    """The durable JSON backend re-reads byte-identically after a reload.

    Simulates a process restart: write through one cache, then construct a fresh
    cache over the *same* file (re-loading from disk) and assert the re-read is
    bit-for-bit identical.
    """

    path = tmp_path_factory.mktemp("emb_cache") / "cache.json"

    writer = EmbeddingCache(JsonFileCacheBackend(path))
    writer.put(model_id, text, vector)

    expected = _packed([float(v) for v in vector])

    # Re-read through the same in-memory cache.
    same_process = writer.get(model_id, text)
    assert same_process is not None
    assert _packed(same_process) == expected

    # Re-read through a freshly constructed cache that reloads from the file.
    reloaded = EmbeddingCache(JsonFileCacheBackend(path))
    after_reload = reloaded.get(model_id, text)
    assert after_reload is not None
    assert _packed(after_reload) == expected
