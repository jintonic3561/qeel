"""get_workspace()のユニットテスト

TDD: RED → GREEN → REFACTOR
"""

import os
from pathlib import Path

import pytest


def test_get_workspace_returns_cwd_when_env_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """環境変数未設定時にカレントディレクトリを返す"""
    from qeel.utils.workspace import get_workspace

    # 環境変数を削除
    monkeypatch.delenv("QEEL_WORKSPACE", raising=False)

    result = get_workspace()
    assert result == Path.cwd()


def test_get_workspace_returns_env_path_when_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """環境変数設定時にそのパスを返す"""
    from qeel.utils.workspace import get_workspace

    # 一時ディレクトリを環境変数に設定
    monkeypatch.setenv("QEEL_WORKSPACE", str(tmp_path))

    result = get_workspace()
    assert result == tmp_path


def test_get_workspace_raises_when_path_not_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """存在しないパス指定時にValueErrorをraise"""
    from qeel.utils.workspace import get_workspace

    # 存在しないパスを設定
    non_existent = "/path/to/nonexistent/dir"
    monkeypatch.setenv("QEEL_WORKSPACE", non_existent)

    with pytest.raises(ValueError, match="QEEL_WORKSPACEで指定されたパスが存在しないか、ディレクトリではありません"):
        get_workspace()
