"""シグナル計算の統合テスト

TDD: RED → GREEN → REFACTOR
MockDataSourceからデータを取得し、シグナル計算を実行する統合テスト。
"""

from datetime import datetime
from pathlib import Path

import polars as pl

from qeel.config.models import DataSourceConfig
from qeel.data_sources.mock import MockDataSource
from qeel.examples.signals.moving_average import (
    MovingAverageCrossCalculator,
    MovingAverageCrossParams,
)
from qeel.schemas.validators import SignalSchema


class TestCalculatorWithMockDataSource:
    """MockDataSourceとの統合テスト"""

    def _create_mock_data(self) -> pl.DataFrame:
        """テスト用のモックデータを作成"""
        dates = [datetime(2024, 1, i) for i in range(1, 31)]

        data = []
        for symbol in ["AAPL", "GOOGL"]:
            base_price = 100.0 if symbol == "AAPL" else 200.0
            for i, dt in enumerate(dates):
                data.append(
                    {
                        "datetime": dt,
                        "symbol": symbol,
                        "open": base_price + i * 0.5,
                        "high": base_price + i * 0.5 + 1.0,
                        "low": base_price + i * 0.5 - 0.5,
                        "close": base_price + i * 0.5 + 0.3,
                        "volume": 1000000 + i * 10000,
                    }
                )

        return pl.DataFrame(data)

    def test_calculator_with_mock_data_source(self) -> None:
        """MockDataSourceからデータを取得し、シグナル計算を実行"""
        # DataSourceConfigの設定
        config = DataSourceConfig(
            name="ohlcv",
            datetime_column="datetime",
            offset_seconds=0,
            window_seconds=86400 * 30,  # 30日
            source_type="custom",
            source_path=Path("/mock/path"),
        )

        # モックデータを作成
        mock_data = self._create_mock_data()

        # MockDataSourceを使用してデータを取得
        data_source = MockDataSource(config=config, data=mock_data)
        ohlcv = data_source.fetch(
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 30),
            symbols=["AAPL", "GOOGL"],
        )

        # シグナル計算実行
        params = MovingAverageCrossParams(short_window=5, long_window=10)
        calculator = MovingAverageCrossCalculator(params=params)

        signals = calculator.calculate({"ohlcv": ohlcv})

        # 結果検証
        assert isinstance(signals, pl.DataFrame)
        assert signals.shape[0] > 0
        assert "datetime" in signals.columns
        assert "symbol" in signals.columns
        assert "signal" in signals.columns

    def test_calculator_output_schema_valid_for_context(self) -> None:
        """シグナル出力がSignalSchemaに準拠し、Context.signalsに設定可能な形式であることを確認

        Note:
            Context自体は006で実装予定だが、SignalSchemaに準拠していれば
            Context.signalsに設定可能。
        """
        # DataSourceConfigの設定
        config = DataSourceConfig(
            name="ohlcv",
            datetime_column="datetime",
            offset_seconds=0,
            window_seconds=86400 * 30,
            source_type="custom",
            source_path=Path("/mock/path"),
        )

        mock_data = self._create_mock_data()
        data_source = MockDataSource(config=config, data=mock_data)
        ohlcv = data_source.fetch(
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 30),
            symbols=["AAPL", "GOOGL"],
        )

        # シグナル計算実行
        params = MovingAverageCrossParams(short_window=5, long_window=10)
        calculator = MovingAverageCrossCalculator(params=params)
        signals = calculator.calculate({"ohlcv": ohlcv})

        # SignalSchemaでバリデーションがパスすることを確認
        validated = SignalSchema.validate(signals)
        assert validated.shape == signals.shape

        # datetime列がpl.Datetime型であることを確認
        assert signals["datetime"].dtype == pl.Datetime
        # symbol列がpl.String型であることを確認
        assert signals["symbol"].dtype == pl.String
        # signal列がpl.Float64型であることを確認
        assert signals["signal"].dtype == pl.Float64
