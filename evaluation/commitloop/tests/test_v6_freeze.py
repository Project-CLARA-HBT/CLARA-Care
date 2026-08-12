from pathlib import Path

import pytest

from evaluation.commitloop import v6_freeze


def test_v6_freeze_rejects_tracked_worktree_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(v6_freeze, "_tracked_worktree_clean", lambda _: False)
    with pytest.raises(v6_freeze.V6FreezeError, match="clean_tracked"):
        v6_freeze.create_v6_freeze(output_dir=tmp_path / "freeze", repository_root=root)
