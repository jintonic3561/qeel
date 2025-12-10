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


class TestFullExitOrderCreator:
    """FullExitOrderCreatorのテスト"""

    def test_full_exit_params_default(self) -> None:
        """FullExitParamsのデフォルト値確認"""
        from qeel.exit_order_creators.full_exit import FullExitParams

        params = FullExitParams()
        assert params.exit_threshold == 1.0

    def test_full_exit_params_custom(self) -> None:
        """FullExitParamsのカスタム値確認"""
        from qeel.exit_order_creators.full_exit import FullExitParams

        params = FullExitParams(exit_threshold=0.5)
        assert params.exit_threshold == 0.5

    def test_full_exit_params_validation(self) -> None:
        """FullExitParamsのバリデーション確認"""
        from pydantic import ValidationError

        from qeel.exit_order_creators.full_exit import FullExitParams

        # 範囲外の値
        with pytest.raises(ValidationError):
            FullExitParams(exit_threshold=-0.1)

        with pytest.raises(ValidationError):
            FullExitParams(exit_threshold=1.1)

    def test_full_exit_all_positions(self) -> None:
        """保有ポジション全決済の注文が生成される"""
        from qeel.exit_order_creators.full_exit import (
            FullExitOrderCreator,
            FullExitParams,
        )

        params = FullExitParams(exit_threshold=1.0)
        creator = FullExitOrderCreator(params=params)

        positions = pl.DataFrame(
            {
                "symbol": ["AAPL", "GOOGL"],
                "quantity": [100.0, 50.0],
                "avg_price": [150.0, 2500.0],
            }
        )
        ohlcv = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1), datetime(2024, 1, 1)],
                "symbol": ["AAPL", "GOOGL"],
                "open": [150.0, 2500.0],
                "high": [155.0, 2550.0],
                "low": [148.0, 2480.0],
                "close": [153.0, 2520.0],
                "volume": [1000000, 500000],
            }
        )

        orders = creator.create(positions, ohlcv)

        assert orders.height == 2
        assert set(orders["symbol"].to_list()) == {"AAPL", "GOOGL"}
        # 買いポジションは売り注文
        aapl_order = orders.filter(pl.col("symbol") == "AAPL")
        assert aapl_order["side"][0] == "sell"
        assert aapl_order["quantity"][0] == 100.0
        assert aapl_order["order_type"][0] == "market"
        assert aapl_order["price"][0] is None

    def test_full_exit_market_order(self) -> None:
        """成行注文（order_type="market", price=None）が生成される"""
        from qeel.exit_order_creators.full_exit import (
            FullExitOrderCreator,
            FullExitParams,
        )

        params = FullExitParams()
        creator = FullExitOrderCreator(params=params)

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

        orders = creator.create(positions, ohlcv)

        assert orders["order_type"][0] == "market"
        assert orders["price"][0] is None

    def test_full_exit_long_position_sell(self) -> None:
        """買いポジションは売りで決済される"""
        from qeel.exit_order_creators.full_exit import (
            FullExitOrderCreator,
            FullExitParams,
        )

        params = FullExitParams()
        creator = FullExitOrderCreator(params=params)

        # 買いポジション（quantity > 0）
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

        orders = creator.create(positions, ohlcv)
        assert orders["side"][0] == "sell"

    def test_full_exit_short_position_buy(self) -> None:
        """売りポジションは買いで決済される"""
        from qeel.exit_order_creators.full_exit import (
            FullExitOrderCreator,
            FullExitParams,
        )

        params = FullExitParams()
        creator = FullExitOrderCreator(params=params)

        # 売りポジション（quantity < 0）
        positions = pl.DataFrame(
            {"symbol": ["AAPL"], "quantity": [-100.0], "avg_price": [150.0]}
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

        orders = creator.create(positions, ohlcv)
        assert orders["side"][0] == "buy"
        assert orders["quantity"][0] == 100.0  # 絶対値

    def test_full_exit_threshold_partial(self) -> None:
        """exit_thresholdに応じて決済数量が調整される"""
        from qeel.exit_order_creators.full_exit import (
            FullExitOrderCreator,
            FullExitParams,
        )

        params = FullExitParams(exit_threshold=0.5)  # 50%決済
        creator = FullExitOrderCreator(params=params)

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

        orders = creator.create(positions, ohlcv)
        assert orders["quantity"][0] == 50.0  # 100 * 0.5

    def test_full_exit_empty_positions(self) -> None:
        """空のポジションに対して空のDataFrameを返す"""
        from qeel.exit_order_creators.full_exit import (
            FullExitOrderCreator,
            FullExitParams,
        )

        params = FullExitParams()
        creator = FullExitOrderCreator(params=params)

        positions = pl.DataFrame(
            {
                "symbol": pl.Series([], dtype=pl.String),
                "quantity": pl.Series([], dtype=pl.Float64),
                "avg_price": pl.Series([], dtype=pl.Float64),
            }
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

        orders = creator.create(positions, ohlcv)
        assert orders.height == 0

    def test_full_exit_skip_no_price_data(self) -> None:
        """価格データがない銘柄がスキップされる"""
        from qeel.exit_order_creators.full_exit import (
            FullExitOrderCreator,
            FullExitParams,
        )

        params = FullExitParams()
        creator = FullExitOrderCreator(params=params)

        # AAPLとGOOGLのポジションがあるが、OHLCVにはAAPLのみ
        positions = pl.DataFrame(
            {
                "symbol": ["AAPL", "GOOGL"],
                "quantity": [100.0, 50.0],
                "avg_price": [150.0, 2500.0],
            }
        )
        ohlcv = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)],
                "symbol": ["AAPL"],  # GOOGLなし
                "open": [150.0],
                "high": [155.0],
                "low": [148.0],
                "close": [153.0],
                "volume": [1000000],
            }
        )

        orders = creator.create(positions, ohlcv)

        assert orders.height == 1
        assert orders["symbol"][0] == "AAPL"

    def test_full_exit_skip_zero_quantity(self) -> None:
        """quantity=0のポジションがスキップされる"""
        from qeel.exit_order_creators.full_exit import (
            FullExitOrderCreator,
            FullExitParams,
        )

        params = FullExitParams()
        creator = FullExitOrderCreator(params=params)

        positions = pl.DataFrame(
            {
                "symbol": ["AAPL", "GOOGL"],
                "quantity": [100.0, 0.0],  # GOOGLはquantity=0
                "avg_price": [150.0, 2500.0],
            }
        )
        ohlcv = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1), datetime(2024, 1, 1)],
                "symbol": ["AAPL", "GOOGL"],
                "open": [150.0, 2500.0],
                "high": [155.0, 2550.0],
                "low": [148.0, 2480.0],
                "close": [153.0, 2520.0],
                "volume": [1000000, 500000],
            }
        )

        orders = creator.create(positions, ohlcv)

        assert orders.height == 1
        assert orders["symbol"][0] == "AAPL"
