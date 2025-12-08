"""BaseDataSource ABCのテスト

TDD: RED -> GREEN -> REFACTOR
data-model.mdとcontracts/base_data_source.mdを参照
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl
import pytest

from qeel.config import DataSourceConfig

if TYPE_CHECKING:
    from qeel.data_sources.base import BaseDataSource


class TestBaseDataSourceCannotInstantiate:
    """ABCが直接インスタンス化できないことを確認"""

    def test_base_data_source_cannot_instantiate(self) -> None:
        """ABCは直接インスタンス化不可"""
        from qeel.data_sources.base import BaseDataSource

        config = DataSourceConfig(
            name="test",
            datetime_column="datetime",
            offset_seconds=0,
            window_seconds=86400,
            source_type="parquet",
            source_path=Path("test.parquet"),
        )

        with pytest.raises(TypeError):
            BaseDataSource(config=config)  # type: ignore[abstract]


class ConcreteDataSource:
    """テスト用の具象DataSourceスタブ

    ヘルパーメソッドをテストするために使用する。
    """

    def __init__(self, config: DataSourceConfig, mock_data: pl.DataFrame | None = None) -> None:
        from qeel.data_sources.base import BaseDataSource

        # BaseDataSourceを継承した具象クラスを動的に作成
        class _ConcreteDataSource(BaseDataSource):
            def __init__(
                self,
                config: DataSourceConfig,
                mock_data: pl.DataFrame | None = None,
            ) -> None:
                super().__init__(config=config)
                self._mock_data = mock_data

            def fetch(self, start: datetime, end: datetime, symbols: list[str]) -> pl.DataFrame:
                if self._mock_data is None:
                    return pl.DataFrame()
                return self._mock_data

        self._instance = _ConcreteDataSource(config=config, mock_data=mock_data)

    @property
    def instance(self) -> "BaseDataSource":
        return self._instance


class TestNormalizeDatetimeColumn:
    """_normalize_datetime_column()ヘルパーメソッドのテスト"""

    @pytest.fixture
    def config_with_different_datetime_column(self) -> DataSourceConfig:
        """datetime列名が"datetime"以外の設定"""
        return DataSourceConfig(
            name="test",
            datetime_column="timestamp",
            offset_seconds=0,
            window_seconds=86400,
            source_type="parquet",
            source_path=Path("test.parquet"),
        )

    @pytest.fixture
    def config_with_standard_datetime_column(self) -> DataSourceConfig:
        """datetime列名が"datetime"の設定"""
        return DataSourceConfig(
            name="test",
            datetime_column="datetime",
            offset_seconds=0,
            window_seconds=86400,
            source_type="parquet",
            source_path=Path("test.parquet"),
        )

    def test_normalize_datetime_column_renames(self, config_with_different_datetime_column: DataSourceConfig) -> None:
        """datetime_columnが"datetime"以外の場合リネームされる"""
        ds = ConcreteDataSource(config=config_with_different_datetime_column)

        df = pl.DataFrame(
            {
                "timestamp": [datetime(2023, 1, 1)],
                "symbol": ["AAPL"],
            }
        )

        result = ds.instance._normalize_datetime_column(df)

        assert "datetime" in result.columns
        assert "timestamp" not in result.columns
        assert result["datetime"].dtype == pl.Datetime

    def test_normalize_datetime_column_casts_to_datetime(
        self, config_with_different_datetime_column: DataSourceConfig
    ) -> None:
        """型がDatetimeでない場合キャストされる"""
        ds = ConcreteDataSource(config=config_with_different_datetime_column)

        # 文字列として日時を格納
        df = pl.DataFrame(
            {
                "timestamp": ["2023-01-01 00:00:00"],
                "symbol": ["AAPL"],
            }
        )

        result = ds.instance._normalize_datetime_column(df)

        assert "datetime" in result.columns
        assert result["datetime"].dtype == pl.Datetime

    def test_normalize_datetime_column_already_datetime(
        self, config_with_standard_datetime_column: DataSourceConfig
    ) -> None:
        """すでに"datetime"列の場合は変更なし"""
        ds = ConcreteDataSource(config=config_with_standard_datetime_column)

        df = pl.DataFrame(
            {
                "datetime": [datetime(2023, 1, 1)],
                "symbol": ["AAPL"],
            }
        )

        result = ds.instance._normalize_datetime_column(df)

        assert "datetime" in result.columns
        assert result["datetime"].dtype == pl.Datetime
        # 元のDataFrameと同じ
        assert result.equals(df)

    def test_normalize_datetime_column_missing_column(
        self, config_with_different_datetime_column: DataSourceConfig
    ) -> None:
        """指定されたdatetime_columnがDataFrameに存在しない場合KeyErrorをraise"""
        ds = ConcreteDataSource(config=config_with_different_datetime_column)

        df = pl.DataFrame(
            {
                "other_column": [datetime(2023, 1, 1)],
                "symbol": ["AAPL"],
            }
        )

        with pytest.raises(KeyError):
            ds.instance._normalize_datetime_column(df)


class TestAdjustWindowForOffset:
    """_adjust_window_for_offset()ヘルパーメソッドのテスト"""

    @pytest.fixture
    def config_with_positive_offset(self) -> DataSourceConfig:
        """正のオフセット設定"""
        return DataSourceConfig(
            name="test",
            datetime_column="datetime",
            offset_seconds=3600,  # 1時間
            window_seconds=86400,
            source_type="parquet",
            source_path=Path("test.parquet"),
        )

    @pytest.fixture
    def config_with_zero_offset(self) -> DataSourceConfig:
        """オフセット0の設定"""
        return DataSourceConfig(
            name="test",
            datetime_column="datetime",
            offset_seconds=0,
            window_seconds=86400,
            source_type="parquet",
            source_path=Path("test.parquet"),
        )

    @pytest.fixture
    def config_with_negative_offset(self) -> DataSourceConfig:
        """負のオフセット設定"""
        return DataSourceConfig(
            name="test",
            datetime_column="datetime",
            offset_seconds=-3600,  # -1時間
            window_seconds=86400,
            source_type="parquet",
            source_path=Path("test.parquet"),
        )

    def test_adjust_window_for_offset_positive(self, config_with_positive_offset: DataSourceConfig) -> None:
        """正のoffset_secondsでwindowが過去方向に調整される"""
        ds = ConcreteDataSource(config=config_with_positive_offset)

        start = datetime(2023, 1, 1, 10, 0, 0)
        end = datetime(2023, 1, 1, 11, 0, 0)

        adjusted_start, adjusted_end = ds.instance._adjust_window_for_offset(start, end)

        # 1時間オフセットなので1時間過去に調整される
        assert adjusted_start == datetime(2023, 1, 1, 9, 0, 0)
        assert adjusted_end == datetime(2023, 1, 1, 10, 0, 0)

    def test_adjust_window_for_offset_zero(self, config_with_zero_offset: DataSourceConfig) -> None:
        """offset_seconds=0の場合windowは変化なし"""
        ds = ConcreteDataSource(config=config_with_zero_offset)

        start = datetime(2023, 1, 1, 10, 0, 0)
        end = datetime(2023, 1, 1, 11, 0, 0)

        adjusted_start, adjusted_end = ds.instance._adjust_window_for_offset(start, end)

        assert adjusted_start == start
        assert adjusted_end == end

    def test_adjust_window_for_offset_negative(self, config_with_negative_offset: DataSourceConfig) -> None:
        """負のoffset_secondsでwindowが未来方向に調整される"""
        ds = ConcreteDataSource(config=config_with_negative_offset)

        start = datetime(2023, 1, 1, 10, 0, 0)
        end = datetime(2023, 1, 1, 11, 0, 0)

        adjusted_start, adjusted_end = ds.instance._adjust_window_for_offset(start, end)

        # -1時間オフセットなので1時間未来に調整される
        assert adjusted_start == datetime(2023, 1, 1, 11, 0, 0)
        assert adjusted_end == datetime(2023, 1, 1, 12, 0, 0)

    def test_adjust_window_prevents_data_leak(self, config_with_positive_offset: DataSourceConfig) -> None:
        """offset_seconds適用後のwindowでフィルタリングした場合、未来データが含まれないことを確認"""
        ds = ConcreteDataSource(config=config_with_positive_offset)

        # 現在時刻を10:00とする
        current_time = datetime(2023, 1, 1, 10, 0, 0)
        start = current_time - timedelta(hours=1)  # 09:00
        end = current_time  # 10:00

        adjusted_start, adjusted_end = ds.instance._adjust_window_for_offset(start, end)

        # 1時間オフセットなので、実際に取得するのは08:00-09:00のデータ
        # つまり10:00時点で見ると、09:00以降のデータは含まれない（リーク防止）
        assert adjusted_end < current_time


class TestFilterByDatetimeAndSymbols:
    """_filter_by_datetime_and_symbols()ヘルパーメソッドのテスト"""

    @pytest.fixture
    def config(self) -> DataSourceConfig:
        return DataSourceConfig(
            name="test",
            datetime_column="datetime",
            offset_seconds=0,
            window_seconds=86400,
            source_type="parquet",
            source_path=Path("test.parquet"),
        )

    @pytest.fixture
    def sample_dataframe(self) -> pl.DataFrame:
        """テスト用サンプルDataFrame"""
        return pl.DataFrame(
            {
                "datetime": [
                    datetime(2023, 1, 1, 9, 0, 0),
                    datetime(2023, 1, 1, 10, 0, 0),
                    datetime(2023, 1, 1, 11, 0, 0),
                    datetime(2023, 1, 1, 12, 0, 0),
                ],
                "symbol": ["AAPL", "GOOG", "AAPL", "MSFT"],
                "close": [100.0, 200.0, 101.0, 300.0],
            }
        )

    def test_filter_by_datetime_and_symbols_filters_correctly(
        self, config: DataSourceConfig, sample_dataframe: pl.DataFrame
    ) -> None:
        """datetime範囲とsymbolsで正しくフィルタリング"""
        ds = ConcreteDataSource(config=config)

        start = datetime(2023, 1, 1, 9, 30, 0)
        end = datetime(2023, 1, 1, 11, 30, 0)
        symbols = ["AAPL", "GOOG"]

        result = ds.instance._filter_by_datetime_and_symbols(sample_dataframe, start, end, symbols)

        # 10:00のAAPLとGOOG、11:00のAAPLのみ
        assert len(result) == 2
        assert set(result["symbol"].to_list()) == {"AAPL", "GOOG"}
        # 09:00のAAPLは範囲外、12:00のMSFTはsymbols外
        assert datetime(2023, 1, 1, 9, 0, 0) not in result["datetime"].to_list()

    def test_filter_by_datetime_and_symbols_empty_result(
        self, config: DataSourceConfig, sample_dataframe: pl.DataFrame
    ) -> None:
        """条件に一致するデータがない場合は空DataFrame"""
        ds = ConcreteDataSource(config=config)

        start = datetime(2023, 1, 2, 0, 0, 0)  # 翌日
        end = datetime(2023, 1, 2, 23, 59, 59)
        symbols = ["AAPL"]

        result = ds.instance._filter_by_datetime_and_symbols(sample_dataframe, start, end, symbols)

        assert len(result) == 0

    def test_filter_by_datetime_and_symbols_empty_symbols(
        self, config: DataSourceConfig, sample_dataframe: pl.DataFrame
    ) -> None:
        """symbols引数が空リストの場合、空DataFrameを返す"""
        ds = ConcreteDataSource(config=config)

        start = datetime(2023, 1, 1, 0, 0, 0)
        end = datetime(2023, 1, 1, 23, 59, 59)
        symbols: list[str] = []

        result = ds.instance._filter_by_datetime_and_symbols(sample_dataframe, start, end, symbols)

        assert len(result) == 0


# =============================================================================
# MockDataSource Tests (T049)
# =============================================================================


class TestMockDataSource:
    """MockDataSourceのテスト

    テスト用モックデータソースの動作を確認する。
    contracts/base_data_source.md参照。
    """

    @pytest.fixture
    def config(self) -> DataSourceConfig:
        """テスト用設定"""
        return DataSourceConfig(
            name="mock_ohlcv",
            datetime_column="datetime",
            offset_seconds=0,
            window_seconds=86400,
            source_type="custom",
            source_path=Path("mock"),
        )

    @pytest.fixture
    def mock_data(self) -> pl.DataFrame:
        """モックデータ"""
        return pl.DataFrame(
            {
                "datetime": [
                    datetime(2023, 1, 1, 9, 0, 0),
                    datetime(2023, 1, 1, 10, 0, 0),
                    datetime(2023, 1, 1, 11, 0, 0),
                    datetime(2023, 1, 2, 9, 0, 0),
                ],
                "symbol": ["AAPL", "GOOG", "AAPL", "MSFT"],
                "open": [99.0, 199.0, 100.0, 299.0],
                "high": [101.0, 201.0, 102.0, 301.0],
                "low": [98.0, 198.0, 99.0, 298.0],
                "close": [100.0, 200.0, 101.0, 300.0],
                "volume": [1000, 2000, 1100, 3000],
            }
        )

    def test_mock_data_source_returns_dataframe(self, config: DataSourceConfig, mock_data: pl.DataFrame) -> None:
        """fetch()がPolars DataFrameを返す"""
        from qeel.data_sources.mock import MockDataSource

        ds = MockDataSource(config=config, data=mock_data)

        result = ds.fetch(
            start=datetime(2023, 1, 1, 0, 0, 0),
            end=datetime(2023, 1, 2, 23, 59, 59),
            symbols=["AAPL", "GOOG", "MSFT"],
        )

        assert isinstance(result, pl.DataFrame)
        assert len(result) > 0

    def test_mock_data_source_respects_symbols(self, config: DataSourceConfig, mock_data: pl.DataFrame) -> None:
        """指定されたsymbolsのデータのみ返す"""
        from qeel.data_sources.mock import MockDataSource

        ds = MockDataSource(config=config, data=mock_data)

        result = ds.fetch(
            start=datetime(2023, 1, 1, 0, 0, 0),
            end=datetime(2023, 1, 2, 23, 59, 59),
            symbols=["AAPL"],
        )

        # AAPLのみ（2行）
        assert len(result) == 2
        assert all(s == "AAPL" for s in result["symbol"].to_list())

    def test_mock_data_source_respects_datetime_range(self, config: DataSourceConfig, mock_data: pl.DataFrame) -> None:
        """指定されたdatetime範囲内のデータを返す"""
        from qeel.data_sources.mock import MockDataSource

        ds = MockDataSource(config=config, data=mock_data)

        # 1/1のみ
        result = ds.fetch(
            start=datetime(2023, 1, 1, 0, 0, 0),
            end=datetime(2023, 1, 1, 23, 59, 59),
            symbols=["AAPL", "GOOG", "MSFT"],
        )

        # 1/1のデータは3行（AAPL, GOOG, AAPL）
        assert len(result) == 3
        # MSFTは1/2なので含まれない
        assert "MSFT" not in result["symbol"].to_list()

    def test_mock_data_source_returns_empty_when_no_match(
        self, config: DataSourceConfig, mock_data: pl.DataFrame
    ) -> None:
        """条件に一致するデータがない場合は空DataFrame"""
        from qeel.data_sources.mock import MockDataSource

        ds = MockDataSource(config=config, data=mock_data)

        result = ds.fetch(
            start=datetime(2023, 1, 3, 0, 0, 0),
            end=datetime(2023, 1, 3, 23, 59, 59),
            symbols=["AAPL"],
        )

        assert len(result) == 0

    def test_mock_data_source_default_schema(self, config: DataSourceConfig) -> None:
        """デフォルトで最小OHLCVスキーマを持つ（datetime, symbol, open, high, low, close, volume）"""
        from qeel.data_sources.mock import MockDataSource

        # データを渡さずに作成
        ds = MockDataSource(config=config)

        result = ds.fetch(
            start=datetime(2023, 1, 1, 0, 0, 0),
            end=datetime(2023, 1, 1, 23, 59, 59),
            symbols=["AAPL", "GOOG"],
        )

        # デフォルトデータが生成される
        assert isinstance(result, pl.DataFrame)
        # 最小OHLCVスキーマを確認
        expected_columns = {"datetime", "symbol", "open", "high", "low", "close", "volume"}
        assert expected_columns.issubset(set(result.columns))
