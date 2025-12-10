"""BaseExitOrderCreatorとFullExitOrderCreatorのテスト

TDDに従い、テストを先に作成する。
"""

from abc import ABC
from datetime import datetime

import polars as pl
import pytest

from qeel.config.params import ExitOrderCreatorParams
from qeel.exit_order_creators.base import BaseExitOrderCreator


class TestBaseExitOrderCreatorValidation:
    """BaseExitOrderCreatorのバリデーションテスト"""

    def test_validate_inputs_success(self) -> None:
        """正常な入力でバリデーションが成功する"""

        class ConcreteCreator(BaseExitOrderCreator):
            def create(
                self,
                current_positions: pl.DataFrame,
                ohlcv: pl.DataFrame,
            ) -> pl.DataFrame:
                self._validate_inputs(current_positions, ohlcv)
                return pl.DataFrame(
                    {
                        "symbol": ["AAPL"],
                        "side": ["sell"],
                        "quantity": [100.0],
                        "price": [None],
                        "order_type": ["market"],
                    }
                )

        params = ExitOrderCreatorParams()
        creator = ConcreteCreator(params=params)

        positions = pl.DataFrame(
            {"symbol": ["AAPL"], "quantity": [100.0], "avg_price": [150.0]}
        )
        ohlcv = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)],
                "symbol": ["AAPL"],
                "open": [150.0],
                "high": [155.0],
                "low": [148.0],
                "close": [153.0],
                "volume": [1000000],
            }
        )

        # バリデーションが成功することを確認
        result = creator.create(positions, ohlcv)
        assert result.height == 1

    def test_validate_inputs_invalid_position_schema(self) -> None:
        """ポジションスキーマが不正な場合にValueErrorが発生する"""

        class ConcreteCreator(BaseExitOrderCreator):
            def create(
                self,
                current_positions: pl.DataFrame,
                ohlcv: pl.DataFrame,
            ) -> pl.DataFrame:
                self._validate_inputs(current_positions, ohlcv)
                return pl.DataFrame()

        params = ExitOrderCreatorParams()
        creator = ConcreteCreator(params=params)

        # quantity列が欠けている
        positions = pl.DataFrame({"symbol": ["AAPL"], "avg_price": [150.0]})
        ohlcv = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)],
                "symbol": ["AAPL"],
                "open": [150.0],
                "high": [155.0],
                "low": [148.0],
                "close": [153.0],
                "volume": [1000000],
            }
        )

        with pytest.raises(ValueError, match="必須列が不足しています"):
            creator.create(positions, ohlcv)

    def test_validate_inputs_invalid_ohlcv_schema(self) -> None:
        """OHLCVスキーマが不正な場合にValueErrorが発生する"""

        class ConcreteCreator(BaseExitOrderCreator):
            def create(
                self,
                current_positions: pl.DataFrame,
                ohlcv: pl.DataFrame,
            ) -> pl.DataFrame:
                self._validate_inputs(current_positions, ohlcv)
                return pl.DataFrame()

        params = ExitOrderCreatorParams()
        creator = ConcreteCreator(params=params)

        positions = pl.DataFrame(
            {"symbol": ["AAPL"], "quantity": [100.0], "avg_price": [150.0]}
        )
        # close列が欠けている
        ohlcv = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)],
                "symbol": ["AAPL"],
                "open": [150.0],
                "high": [155.0],
                "low": [148.0],
                "volume": [1000000],
            }
        )

        with pytest.raises(ValueError, match="必須列が不足しています"):
            creator.create(positions, ohlcv)


class TestBaseExitOrderCreatorABC:
    """BaseExitOrderCreatorのABC継承テスト"""

    def test_is_abstract_class(self) -> None:
        """BaseExitOrderCreatorが抽象基底クラスであることを確認"""
        assert issubclass(BaseExitOrderCreator, ABC)

    def test_cannot_instantiate_directly(self) -> None:
        """BaseExitOrderCreatorは直接インスタンス化できない"""
        with pytest.raises(TypeError, match="abstract"):
            BaseExitOrderCreator(params=ExitOrderCreatorParams())  # type: ignore

    def test_must_implement_create(self) -> None:
        """createメソッドの実装が必要"""

        # 抽象メソッドを実装しないサブクラス
        class IncompleteCreator(BaseExitOrderCreator):
            pass

        with pytest.raises(TypeError, match="abstract"):
            IncompleteCreator(params=ExitOrderCreatorParams())  # type: ignore

    def test_subclass_with_create_works(self) -> None:
        """createメソッドを実装したサブクラスはインスタンス化できる"""

        class CompleteCreator(BaseExitOrderCreator):
            def create(
                self,
                current_positions: pl.DataFrame,
                ohlcv: pl.DataFrame,
            ) -> pl.DataFrame:
                return pl.DataFrame(
                    {
                        "symbol": ["TEST"],
                        "side": ["sell"],
                        "quantity": [100.0],
                        "price": [None],
                        "order_type": ["market"],
                    }
                )

        params = ExitOrderCreatorParams()
        creator = CompleteCreator(params=params)
        assert creator.params == params
