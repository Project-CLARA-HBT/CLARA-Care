"""Timeout-floor invariants for CLARA_API ML request timeouts.

These helpers keep the API-side ML request timeout from ever dropping below the
downstream CLARA_ML synthesis timeout for the same request class (Requirement
2.4). They are intentionally pure so they can be exercised directly by unit and
property tests (Property 3) and reused by the startup configuration guard.
"""

from __future__ import annotations

# The synchronous research path always waits at least this long, regardless of
# the configured ``ml_research_timeout_seconds``. This is the single source of
# truth for the floor used by the ``/research/tier2`` proxy call.
SYNC_RESEARCH_TIMEOUT_FLOOR_SECONDS: float = 600.0


class TimeoutFloorError(RuntimeError):
    """Raised when an API ML timeout is configured below its synthesis floor."""


def assert_timeout_floor(api_timeout: float, ml_synthesis_timeout: float) -> None:
    """Assert the API ML request timeout never sits below the ML synthesis timeout.

    Args:
        api_timeout: The timeout the API applies to its ML request.
        ml_synthesis_timeout: The downstream CLARA_ML synthesis timeout for the
            same request class.

    Raises:
        TimeoutFloorError: If ``api_timeout`` is below ``ml_synthesis_timeout``.
    """

    if api_timeout < ml_synthesis_timeout:
        raise TimeoutFloorError(
            "API ML timeout "
            f"{api_timeout}s is below the ML synthesis timeout {ml_synthesis_timeout}s"
        )


def resolve_sync_research_timeout(ml_research_timeout_seconds: float) -> float:
    """Resolve the synchronous-research timeout, applying the 600s floor."""

    return max(float(ml_research_timeout_seconds), SYNC_RESEARCH_TIMEOUT_FLOOR_SECONDS)


def assert_settings_timeout_floors(
    *,
    ml_service_timeout_seconds: float,
    ml_research_timeout_seconds: float,
    deepseek_timeout_seconds: float,
) -> None:
    """Validate every API ML timeout against its synthesis floor.

    - The tier1/chat path uses ``ml_service_timeout_seconds`` and must stay at or
      above the ML DeepSeek synthesis timeout (``deepseek_timeout_seconds``).
    - The synchronous research path uses ``max(ml_research_timeout_seconds, 600)``
      and must stay at or above ``ml_research_timeout_seconds``.

    Raises:
        TimeoutFloorError: If any configured timeout violates its floor.
    """

    assert_timeout_floor(ml_service_timeout_seconds, deepseek_timeout_seconds)
    assert_timeout_floor(
        resolve_sync_research_timeout(ml_research_timeout_seconds),
        ml_research_timeout_seconds,
    )
