"""BaseSignalCalculatorのユニットテスト

TDD: RED → GREEN → REFACTOR
contracts/base_signal_calculator.mdの仕様に準拠。
"""

from datetime import datetime

import polars as pl
import pytest

from qeel.config.params import SignalCalculatorParams


class TestBaseSignalCalculatorABC:
    """BaseSignalCalculator ABCのテスト"""

    def test_base_signal_calculator_cannot_instantiate(self) -> None:
        """ABCは直接インスタンス化できないことを確認"""
        from qeel.calculators.signals.base import BaseSignalCalculator

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            BaseSignalCalculator(params=SignalCalculatorParams())  # type: ignore[abstract]

    def test_calculate_is_abstract_method(self) -> None:
        """calculate()が抽象メソッドであることを確認"""
        from qeel.calculators.signals.base import BaseSignalCalculator
        import inspect

        # calculate メソッドが抽象メソッドとしてマークされていることを確認
        assert hasattr(BaseSignalCalculator, "calculate")
        # ABCの__abstractmethods__に含まれていることを確認
        assert "calculate" in BaseSignalCalculator.__abstractmethods__


class TestValidateOutputHelper:
    """_validate_output() ヘルパーメソッドのテスト

    protectedメソッドはテスト用スタブ経由で検証する。
    """

    def _create_stub_calculator(self) -> "StubSignalCalculator":
        """テスト用スタブCalculatorを作成"""
        from qeel.calculators.signals.base import BaseSignalCalculator

        class StubSignalCalculator(BaseSignalCalculator):
            """テスト用の具象実装"""

            def calculate(self, data_sources: dict[str, pl.DataFrame]) -> pl.DataFrame:
                # 何もしない実装
                return pl.DataFrame()

        return StubSignalCalculator(params=SignalCalculatorParams())

    def test_validate_output_passes_valid_signal(self) -> None:
        """有効なSignalSchemaでバリデーションパス"""
        stub = self._create_stub_calculator()

        valid_signals = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1), datetime(2024, 1, 2)],
                "symbol": ["AAPL", "GOOGL"],
                "signal": [0.5, -0.3],
            }
        )

        result = stub._validate_output(valid_signals)
        assert result.shape == valid_signals.shape

    def test_validate_output_raises_missing_datetime(self) -> None:
        """datetime列欠損でValueError"""
        stub = self._create_stub_calculator()

        invalid_signals = pl.DataFrame(
            {
                "symbol": ["AAPL", "GOOGL"],
                "signal": [0.5, -0.3],
            }
        )

        with pytest.raises(ValueError, match="必須列が不足しています: datetime"):
            stub._validate_output(invalid_signals)

    def test_validate_output_raises_missing_symbol(self) -> None:
        """symbol列欠損でValueError"""
        stub = self._create_stub_calculator()

        invalid_signals = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1), datetime(2024, 1, 2)],
                "signal": [0.5, -0.3],
            }
        )

        with pytest.raises(ValueError, match="必須列が不足しています: symbol"):
            stub._validate_output(invalid_signals)

    def test_validate_output_raises_wrong_dtype(self) -> None:
        """型不一致でValueError"""
        stub = self._create_stub_calculator()

        # symbolがInt型になっている不正なDataFrame
        invalid_signals = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1), datetime(2024, 1, 2)],
                "symbol": [1, 2],  # 不正な型
                "signal": [0.5, -0.3],
            }
        )

        with pytest.raises(ValueError, match="列'symbol'の型が不正です"):
            stub._validate_output(invalid_signals)

    def test_validate_output_allows_extra_columns(self) -> None:
        """追加列（signal, signal_momentum等）は許容"""
        stub = self._create_stub_calculator()

        signals_with_extra = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1), datetime(2024, 1, 2)],
                "symbol": ["AAPL", "GOOGL"],
                "signal": [0.5, -0.3],
                "signal_momentum": [0.1, 0.2],
                "signal_value": [0.8, 0.7],
                "custom_column": ["extra1", "extra2"],
            }
        )

        # エラーなく通過することを確認
        result = stub._validate_output(signals_with_extra)
        assert result.shape == signals_with_extra.shape
        assert "custom_column" in result.columns


class TestParamsStorage:
    """paramsがインスタンスに保存されることのテスト"""

    def test_params_is_stored_in_instance(self) -> None:
        """paramsがインスタンスに保存されることを確認"""
        from qeel.calculators.signals.base import BaseSignalCalculator

        class StubSignalCalculator(BaseSignalCalculator):
            """テスト用の具象実装"""

            def calculate(self, data_sources: dict[str, pl.DataFrame]) -> pl.DataFrame:
                return pl.DataFrame()

        params = SignalCalculatorParams()
        calculator = StubSignalCalculator(params=params)

        assert calculator.params is params


class TestMovingAverageCrossParams:
    """MovingAverageCrossParamsのテスト"""

    def test_moving_average_cross_params_validation(self) -> None:
        """パラメータバリデーション確認（short_window > 0, long_window > 0）"""
        from pydantic import ValidationError

        from qeel.examples.signals.moving_average import MovingAverageCrossParams

        # 正常なパラメータ
        params = MovingAverageCrossParams(short_window=5, long_window=20)
        assert params.short_window == 5
        assert params.long_window == 20

        # short_window <= 0 はエラー
        with pytest.raises(ValidationError):
            MovingAverageCrossParams(short_window=0, long_window=20)

        # long_window <= 0 はエラー
        with pytest.raises(ValidationError):
            MovingAverageCrossParams(short_window=5, long_window=0)

    def test_moving_average_cross_params_short_less_than_long(self) -> None:
        """short_window >= long_windowでValidationError"""
        from pydantic import ValidationError

        from qeel.examples.signals.moving_average import MovingAverageCrossParams

        # short_window >= long_windowはエラー
        with pytest.raises(ValidationError, match="short_windowはlong_windowより小さい"):
            MovingAverageCrossParams(short_window=20, long_window=20)

        with pytest.raises(ValidationError, match="short_windowはlong_windowより小さい"):
            MovingAverageCrossParams(short_window=30, long_window=20)


class TestMovingAverageCrossCalculator:
    """MovingAverageCrossCalculatorのテスト"""

    def _create_mock_ohlcv(self) -> pl.DataFrame:
        """モックOHLCVデータを作成"""
        dates = [datetime(2024, 1, i) for i in range(1, 31)]

        # AAPLとGOOGL の2銘柄分のデータを作成
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

    def test_moving_average_cross_calculate_returns_signal(self) -> None:
        """モックOHLCVからシグナルを計算"""
        from qeel.examples.signals.moving_average import (
            MovingAverageCrossCalculator,
            MovingAverageCrossParams,
        )

        params = MovingAverageCrossParams(short_window=5, long_window=10)
        calculator = MovingAverageCrossCalculator(params=params)

        ohlcv = self._create_mock_ohlcv()
        data_sources = {"ohlcv": ohlcv}

        signals = calculator.calculate(data_sources)

        # 結果はDataFrame
        assert isinstance(signals, pl.DataFrame)
        # 空でない
        assert signals.shape[0] > 0

    def test_moving_average_cross_raises_missing_ohlcv(self) -> None:
        """ohlcvデータソースが欠損でValueError"""
        from qeel.examples.signals.moving_average import (
            MovingAverageCrossCalculator,
            MovingAverageCrossParams,
        )

        params = MovingAverageCrossParams(short_window=5, long_window=10)
        calculator = MovingAverageCrossCalculator(params=params)

        # ohlcvがない
        data_sources: dict[str, pl.DataFrame] = {}

        with pytest.raises(ValueError, match="ohlcvデータソースが必要です"):
            calculator.calculate(data_sources)

    def test_moving_average_cross_output_has_required_columns(self) -> None:
        """出力にdatetime, symbol, signal列が含まれる"""
        from qeel.examples.signals.moving_average import (
            MovingAverageCrossCalculator,
            MovingAverageCrossParams,
        )

        params = MovingAverageCrossParams(short_window=5, long_window=10)
        calculator = MovingAverageCrossCalculator(params=params)

        ohlcv = self._create_mock_ohlcv()
        data_sources = {"ohlcv": ohlcv}

        signals = calculator.calculate(data_sources)

        # 必須列が含まれることを確認
        assert "datetime" in signals.columns
        assert "symbol" in signals.columns
        assert "signal" in signals.columns

    def test_moving_average_cross_output_schema_valid(self) -> None:
        """出力がSignalSchemaに準拠"""
        from qeel.examples.signals.moving_average import (
            MovingAverageCrossCalculator,
            MovingAverageCrossParams,
        )
        from qeel.schemas.validators import SignalSchema

        params = MovingAverageCrossParams(short_window=5, long_window=10)
        calculator = MovingAverageCrossCalculator(params=params)

        ohlcv = self._create_mock_ohlcv()
        data_sources = {"ohlcv": ohlcv}

        signals = calculator.calculate(data_sources)

        # SignalSchemaでバリデーションがパスすることを確認
        validated = SignalSchema.validate(signals)
        assert validated.shape == signals.shape
