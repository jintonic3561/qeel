"""Configuration統合テスト

get_workspace()とConfig.from_toml()の連携テスト。
"""

from pathlib import Path

import pytest


def test_full_config_load_from_toml() -> None:
    """完全なTOMLからConfigロードし、全プロパティにアクセス可能"""
    from qeel.config.models import Config

    config = Config.from_toml(Path("tests/fixtures/valid_config.toml"))

    # General設定
    assert config.general.storage_type == "local"

    # Loop設定
    assert config.loop.frequency.days == 1
    assert config.loop.start_date.year == 2023
    assert config.loop.end_date.year == 2023

    # DataSource設定
    assert len(config.data_sources) == 1
    assert config.data_sources[0].name == "ohlcv"
    assert config.data_sources[0].datetime_column == "timestamp"

    # Cost設定
    assert config.costs.commission_rate == 0.001
    assert config.costs.slippage_bps == 5.0


def test_workspace_and_config_integration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """get_workspace()とConfig.from_toml()の連携"""
    from qeel.config.models import Config
    from qeel.utils.workspace import get_workspace

    # ワークスペース設定
    workspace = tmp_path
    monkeypatch.setenv("QEEL_WORKSPACE", str(workspace))

    # get_workspace()が正しく動作することを確認
    assert get_workspace() == workspace

    # configs/config.tomlを作成
    config_dir = workspace / "configs"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"

    # valid_config.tomlをコピー
    import shutil

    shutil.copy("tests/fixtures/valid_config.toml", config_file)

    # Config.from_toml()がget_workspace()を使用してデフォルトパスを解決
    config = Config.from_toml()
    assert config.general.storage_type == "local"
    assert config.loop.frequency.days == 1
