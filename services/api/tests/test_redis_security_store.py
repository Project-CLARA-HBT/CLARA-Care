from __future__ import annotations

from clara_api.core.redis_security_store import RedisSecurityStore


class _FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}

    def set(self, key: str, value: bytes, *, ex: int) -> bool:
        assert ex > 0
        self.values[key] = value
        return True

    def get(self, key: str) -> bytes | None:
        return self.values.get(key)


def test_opaque_value_helpers_preserve_bytes_and_availability() -> None:
    store = RedisSecurityStore()
    store._client = _FakeRedis()

    assert store.available() is True
    assert store.set_bytes("isolated:key", b"opaque", ttl_seconds=30) is True
    assert store.get_bytes("isolated:key") == b"opaque"
    assert store.get_bytes("isolated:missing") is None
