"""Configuration Modelsのユニットテスト

TDD: RED → GREEN → REFACTOR
data-model.md 1.1-1.4を参照
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError


# DataSourceConfig tests
def test_data_source_config_valid() -> None:
    """正常な設定でバリデーションパス"""
    from qeel.config.models import DataSourceConfig

    config = DataSourceConfig(
        name="ohlcv",
        datetime_column="timestamp",
        offset_seconds=0,
        window_seconds=86400,
        module="qeel.data_sources.mock",
        class_name="MockDataSource",
        source_path="tests/fixtures/ohlcv.parquet",
    )
    assert config.name == "ohlcv"
    assert config.offset_seconds == 0
    assert config.window_seconds == 86400
    assert config.module == "qeel.data_sources.mock"
    assert config.class_name == "MockDataSource"


def test_data_source_config_missing_module() -> None:
    """module未設定でValidationError"""
    from qeel.config.models import DataSourceConfig

    with pytest.raises(ValidationError, match="module"):
        DataSourceConfig(
            name="ohlcv",
            datetime_column="timestamp",
            offset_seconds=0,
            window_seconds=86400,
            class_name="MockDataSource",
            source_path="tests/fixtures/ohlcv.parquet",
        )


# CostConfig tests
def test_cost_config_defaults() -> None:
    """デフォルト値の確認"""
    from qeel.config.models import CostConfig

    config = CostConfig()
    assert config.commission_rate == 0.0
    assert config.slippage_bps == 0.0
    assert config.market_impact_model == "fixed"
    assert config.market_impact_param == 0.0


def test_cost_config_market_fill_price_type_default() -> None:
    """market_fill_price_typeのデフォルト値がnext_openであることを確認"""
    from qeel.config.models import CostConfig

    config = CostConfig()
    assert config.market_fill_price_type == "next_open"


def test_cost_config_market_fill_price_type_current_close() -> None:
    """market_fill_price_type=current_closeでバリデーションパス"""
    from qeel.config.models import CostConfig

    config = CostConfig(market_fill_price_type="current_close")
    assert config.market_fill_price_type == "current_close"


def test_cost_config_market_fill_price_type_invalid() -> None:
    """不正なmarket_fill_price_typeでValidationError"""
    from qeel.config.models import CostConfig

    with pytest.raises(ValidationError, match="market_fill_price_typeは"):
        CostConfig(market_fill_price_type="invalid_type")


def test_cost_config_limit_fill_bar_type_default() -> None:
    """limit_fill_bar_typeのデフォルト値がnext_barであることを確認"""
    from qeel.config.models import CostConfig

    config = CostConfig()
    assert config.limit_fill_bar_type == "next_bar"


def test_cost_config_limit_fill_bar_type_current_bar() -> None:
    """limit_fill_bar_type=current_barでバリデーションパス"""
    from qeel.config.models import CostConfig

    config = CostConfig(limit_fill_bar_type="current_bar")
    assert config.limit_fill_bar_type == "current_bar"


def test_cost_config_limit_fill_bar_type_invalid() -> None:
    """不正なlimit_fill_bar_typeでValidationError"""
    from qeel.config.models import CostConfig

    with pytest.raises(ValidationError, match="limit_fill_bar_typeは"):
        CostConfig(limit_fill_bar_type="invalid_type")


def test_cost_config_invalid_market_impact_model() -> None:
    """不正なmarket_impact_modelでValidationError"""
    from qeel.config.models import CostConfig

    with pytest.raises(ValidationError, match="market_impact_modelは"):
        CostConfig(market_impact_model="invalid_model")


# StepTimingConfig tests
def test_step_timing_config_defaults() -> None:
    """デフォルト値の確認"""
    from qeel.config.models import StepTimingConfig

    config = StepTimingConfig()
    assert config.calculate_signals_offset_seconds == 0
    assert config.construct_portfolio_offset_seconds == 0
    assert config.create_entry_orders_offset_seconds == 0
    assert config.create_exit_orders_offset_seconds == 0
    assert config.submit_entry_orders_offset_seconds == 0
    assert config.submit_exit_orders_offset_seconds == 0


# LoopConfig tests
def test_loop_config_frequency_parse_days() -> None:
    """\"1d\"をtimedeltaに変換"""
    from qeel.config.models import LoopConfig

    # NOTE: mypyは静的解析のためPydanticのbefore validatorによる
    # str -> timedelta変換を認識できない。実行時には正しく変換される。
    config = LoopConfig(
        frequency="1d",  # type: ignore[arg-type]
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2023, 12, 31),
    )
    assert config.frequency == timedelta(days=1)


def test_loop_config_frequency_parse_hours() -> None:
    """\"4h\"をtimedeltaに変換"""
    from qeel.config.models import LoopConfig

    config = LoopConfig(
        frequency="4h",  # type: ignore[arg-type]
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2023, 12, 31),
    )
    assert config.frequency == timedelta(hours=4)


def test_loop_config_frequency_parse_weeks() -> None:
    """\"1w\"をtimedeltaに変換"""
    from qeel.config.models import LoopConfig

    config = LoopConfig(
        frequency="1w",  # type: ignore[arg-type]
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2023, 12, 31),
    )
    assert config.frequency == timedelta(weeks=1)


def test_loop_config_frequency_parse_minutes() -> None:
    """\"30m\"をtimedeltaに変換"""
    from qeel.config.models import LoopConfig

    config = LoopConfig(
        frequency="30m",  # type: ignore[arg-type]
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2023, 12, 31),
    )
    assert config.frequency == timedelta(minutes=30)


def test_loop_config_frequency_invalid_format() -> None:
    """不正形式でValidationError"""
    from qeel.config.models import LoopConfig

    with pytest.raises(ValidationError, match="不正なfrequency形式"):
        LoopConfig(
            frequency="invalid",  # type: ignore[arg-type]
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
        )


def test_loop_config_end_before_start() -> None:
    """end_date < start_dateでValidationError"""
    from qeel.config.models import LoopConfig

    with pytest.raises(ValidationError, match="end_dateはstart_dateより後である必要があります"):
        LoopConfig(
            frequency="1d",  # type: ignore[arg-type]
            start_date=datetime(2023, 12, 31),
            end_date=datetime(2023, 1, 1),
        )


# GeneralConfig tests
def test_general_config_local_storage() -> None:
    """storage_type=\"local\"で正常"""
    from qeel.config.models import GeneralConfig

    config = GeneralConfig(strategy_name="my_strategy", storage_type="local")
    assert config.strategy_name == "my_strategy"
    assert config.storage_type == "local"
    assert config.s3_bucket is None
    assert config.s3_region is None


def test_general_config_s3_storage_valid() -> None:
    """storage_type=\"s3\"で必須項目ありで正常"""
    from qeel.config.models import GeneralConfig

    config = GeneralConfig(
        strategy_name="my_strategy",
        storage_type="s3",
        s3_bucket="my-bucket",
        s3_region="ap-northeast-1",
    )
    assert config.strategy_name == "my_strategy"
    assert config.storage_type == "s3"
    assert config.s3_bucket == "my-bucket"
    assert config.s3_region == "ap-northeast-1"


def test_general_config_s3_missing_bucket() -> None:
    """s3でbucket未設定時にValidationError"""
    from qeel.config.models import GeneralConfig

    with pytest.raises(ValidationError, match="s3_bucketは必須"):
        GeneralConfig(strategy_name="my_strategy", storage_type="s3", s3_region="ap-northeast-1")


def test_general_config_s3_missing_region() -> None:
    """s3でregion未設定時にValidationError"""
    from qeel.config.models import GeneralConfig

    with pytest.raises(ValidationError, match="s3_regionは必須"):
        GeneralConfig(strategy_name="my_strategy", storage_type="s3", s3_bucket="my-bucket")


# Config Root Model and TOML Loading tests (Phase 4)
def test_config_from_toml_valid() -> None:
    """正常なTOMLファイルからConfig生成"""
    from qeel.config.models import Config

    config = Config.from_toml(Path("tests/fixtures/valid_config.toml"))
    assert config.general.storage_type == "local"
    assert config.loop.frequency == timedelta(days=1)
    assert len(config.data_sources) == 1
    assert config.data_sources[0].name == "ohlcv"
    assert config.costs.commission_rate == 0.001


def test_config_from_toml_missing_file() -> None:
    """ファイル不存在時にFileNotFoundError"""
    from qeel.config.models import Config

    with pytest.raises(FileNotFoundError):
        Config.from_toml(Path("tests/fixtures/nonexistent.toml"))


def test_config_from_toml_invalid_toml() -> None:
    """不正なTOML形式でエラー"""
    # 不正なTOMLファイルを一時作成
    import tempfile

    from qeel.config.models import Config

    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write("invalid toml syntax [[[")
        invalid_path = Path(f.name)

    try:
        with pytest.raises(Exception):  # TOMLParseError等
            Config.from_toml(invalid_path)
    finally:
        invalid_path.unlink()


def test_config_from_toml_validation_error() -> None:
    """バリデーションエラーでValidationError"""
    from qeel.config.models import Config

    with pytest.raises(ValidationError):
        Config.from_toml(Path("tests/fixtures/invalid_config.toml"))


def test_config_from_toml_default_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """パス未指定時にワークスペース/configs/config.tomlを参照"""
    from qeel.config.models import Config

    # ワークスペース設定
    workspace = tmp_path
    monkeypatch.setenv("QEEL_WORKSPACE", str(workspace))

    # configs/config.tomlを作成
    config_dir = workspace / "configs"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"

    # valid_config.tomlをコピー
    import shutil

    shutil.copy("tests/fixtures/valid_config.toml", config_file)

    # パス未指定でfrom_toml()を呼び出し
    config = Config.from_toml()
    assert config.general.storage_type == "local"
