"""データソース統合テスト

TDD: RED -> GREEN -> REFACTOR
contracts/base_data_source.mdを参照。
"""

from datetime import datetime

import polars as pl
import pytest

from qeel.config import DataSourceConfig
from qeel.data_sources.base import BaseDataSource
from qeel.data_sources.mock import MockDataSource


class TestMockDataSourceWithConfig:
    """DataSourceConfigを使用したMockDataSourceの統合テスト"""

    @pytest.fixture
    def config(self) -> DataSourceConfig:
        """テスト用設定"""
        return DataSourceConfig(
            name="test_ohlcv",
            datetime_column="datetime",
            offset_seconds=3600,  # 1時間オフセット
            window_seconds=86400,
            module="qeel.data_sources.mock",
            class_name="MockDataSource",
            source_path="mock",
        )

    @pytest.fixture
    def mock_data(self) -> pl.DataFrame:
        """モックデータ"""
        return pl.DataFrame(
            {
                "datetime": [
                    datetime(2023, 1, 1, 8, 0, 0),
                    datetime(2023, 1, 1, 9, 0, 0),
                    datetime(2023, 1, 1, 10, 0, 0),
                    datetime(2023, 1, 1, 11, 0, 0),
                ],
                "symbol": ["AAPL", "AAPL", "GOOG", "GOOG"],
                "open": [99.0, 100.0, 199.0, 200.0],
                "high": [101.0, 102.0, 201.0, 202.0],
                "low": [98.0, 99.0, 198.0, 199.0],
                "close": [100.0, 101.0, 200.0, 201.0],
                "volume": [1000, 1100, 2000, 2100],
            }
        )

    def test_mock_data_source_with_config(self, config: DataSourceConfig, mock_data: pl.DataFrame) -> None:
        """DataSourceConfigを使用してMockDataSourceを初期化し、fetch()が正常動作"""
        ds = MockDataSource(config=config, data=mock_data)

        # 設定が正しく保持されていることを確認
        assert ds.config.name == "test_ohlcv"
        assert ds.config.offset_seconds == 3600

        # fetch()が正常に動作
        result = ds.fetch(
            start=datetime(2023, 1, 1, 8, 0, 0),
            end=datetime(2023, 1, 1, 11, 0, 0),
            symbols=["AAPL", "GOOG"],
        )

        assert isinstance(result, pl.DataFrame)
        assert len(result) == 4  # 全データが範囲内


class TestDataSourceHelperChain:
    """ヘルパーメソッドの連鎖使用テスト"""

    @pytest.fixture
    def config_with_offset(self) -> DataSourceConfig:
        """オフセット付き設定"""
        return DataSourceConfig(
            name="test_ohlcv",
            datetime_column="timestamp",  # datetime以外の列名
            offset_seconds=3600,  # 1時間オフセット
            window_seconds=86400,
            module="qeel.data_sources.mock",
            class_name="MockDataSource",
            source_path="mock",
        )

    def test_data_source_helper_chain(self, config_with_offset: DataSourceConfig) -> None:
        """ヘルパーメソッドを連鎖して使用した場合の動作確認

        実際のデータソース実装で使用されるパターンをテスト:
        1. _adjust_window_for_offset() でwindowを調整
        2. _normalize_datetime_column() でdatetime列を正規化
        3. _filter_by_datetime_and_symbols() でフィルタリング
        """

        # カスタムデータソースを作成
        class CustomDataSource(BaseDataSource):
            """ヘルパーメソッド連鎖を使用するカスタムデータソース"""

            def __init__(
                self,
                config: DataSourceConfig,
                raw_data: pl.DataFrame,
            ) -> None:
                super().__init__(config=config)
                self._raw_data = raw_data

            def fetch(self, start: datetime, end: datetime, symbols: list[str]) -> pl.DataFrame:
                # 1. offsetを考慮してwindowを調整
                adjusted_start, adjusted_end = self._adjust_window_for_offset(start, end)

                # 2. datetime列を正規化
                df = self._normalize_datetime_column(self._raw_data)

                # 3. フィルタリング
                df = self._filter_by_datetime_and_symbols(df, adjusted_start, adjusted_end, symbols)

                return df

        # テストデータ（timestamp列を使用）
        raw_data = pl.DataFrame(
            {
                "timestamp": [
                    datetime(2023, 1, 1, 8, 0, 0),
                    datetime(2023, 1, 1, 9, 0, 0),
                    datetime(2023, 1, 1, 10, 0, 0),
                    datetime(2023, 1, 1, 11, 0, 0),
                ],
                "symbol": ["AAPL", "AAPL", "GOOG", "GOOG"],
                "close": [100.0, 101.0, 200.0, 201.0],
            }
        )

        ds = CustomDataSource(config=config_with_offset, raw_data=raw_data)

        # fetch()を実行
        # 元のwindow: 10:00 - 11:00
        # offset 1時間適用後: 09:00 - 10:00
        result = ds.fetch(
            start=datetime(2023, 1, 1, 10, 0, 0),
            end=datetime(2023, 1, 1, 11, 0, 0),
            symbols=["AAPL"],
        )

        # オフセット適用により、09:00 - 10:00のデータが取得される
        # AAPLの09:00のデータのみ（1行）
        assert len(result) == 1
        assert result["symbol"][0] == "AAPL"
        assert result["close"][0] == 101.0

        # datetime列が正規化されていることを確認
        assert "datetime" in result.columns
        assert "timestamp" not in result.columns


class TestDataSourceInheritance:
    """BaseDataSourceの継承テスト"""

    def test_mock_data_source_is_base_data_source(self) -> None:
        """MockDataSourceはBaseDataSourceを継承している"""
        assert issubclass(MockDataSource, BaseDataSource)

    def test_custom_data_source_can_be_created(self) -> None:
        """カスタムデータソースを作成できる"""

        class MyCustomDataSource(BaseDataSource):
            def fetch(self, start: datetime, end: datetime, symbols: list[str]) -> pl.DataFrame:
                return pl.DataFrame(
                    {
                        "datetime": [start],
                        "symbol": [symbols[0] if symbols else "UNKNOWN"],
                        "value": [42.0],
                    }
                )

        config = DataSourceConfig(
            name="custom",
            datetime_column="datetime",
            offset_seconds=0,
            window_seconds=86400,
            module="qeel.data_sources.mock",
            class_name="MockDataSource",
            source_path="custom",
        )

        ds = MyCustomDataSource(config=config)
        result = ds.fetch(
            start=datetime(2023, 1, 1),
            end=datetime(2023, 1, 2),
            symbols=["TEST"],
        )

        assert len(result) == 1
        assert result["symbol"][0] == "TEST"
        assert result["value"][0] == 42.0
