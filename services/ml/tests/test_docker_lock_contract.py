"""Production image dependency-resolution contracts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ml_image_uses_the_committed_frozen_lock() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY services/ml/uv.lock /app/uv.lock" in dockerfile
    assert "uv sync --frozen --no-dev --no-editable" in dockerfile
    assert "pip install --no-cache-dir ." not in dockerfile
