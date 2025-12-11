"""BaseEntryOrderCreatorとEqualWeightEntryOrderCreatorのテスト

TDDに従い、テストを先に作成する。
"""

from abc import ABC
from datetime import datetime

import polars as pl
import pytest

from qeel.config.params import EntryOrderCreatorParams
from qeel.entry_order_creators.base import BaseEntryOrderCreator


class TestBaseEntryOrderCreatorValidation:
    """BaseEntryOrderCreatorのバリデーションテスト"""

    def test_validate_inputs_success(self) -> None:
        """正常な入力でバリデーションが成功する"""

        class ConcreteCreator(BaseEntryOrderCreator):
            def create(
                self,
                portfolio_plan: pl.DataFrame,
                current_positions: pl.DataFrame,
                ohlcv: pl.DataFrame,
            ) -> pl.DataFrame:
                self._validate_inputs(portfolio_plan, current_positions, ohlcv)
                return pl.DataFrame(
                    {
                        "symbol": ["AAPL"],
                        "side": ["buy"],
                        "quantity": [100.0],
                        "price": [None],
                        "order_type": ["market"],
                    }
                )

        params = EntryOrderCreatorParams()
        creator = ConcreteCreator(params=params)

        portfolio_plan = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)],
                "symbol": ["AAPL"],
                "signal_strength": [1.5],
            }
        )
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
        result = creator.create(portfolio_plan, positions, ohlcv)
        assert result.height == 1

    def test_validate_inputs_invalid_portfolio_schema(self) -> None:
        """ポートフォリオスキーマが不正な場合にValueErrorが発生する"""

        class ConcreteCreator(BaseEntryOrderCreator):
            def create(
                self,
                portfolio_plan: pl.DataFrame,
                current_positions: pl.DataFrame,
                ohlcv: pl.DataFrame,
            ) -> pl.DataFrame:
                self._validate_inputs(portfolio_plan, current_positions, ohlcv)
                return pl.DataFrame()

        params = EntryOrderCreatorParams()
        creator = ConcreteCreator(params=params)

        # datetime列が欠けている
        portfolio_plan = pl.DataFrame(
            {"symbol": ["AAPL"], "signal_strength": [1.5]}
        )
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

        with pytest.raises(ValueError, match="必須列が不足しています"):
            creator.create(portfolio_plan, positions, ohlcv)

    def test_validate_inputs_invalid_position_schema(self) -> None:
        """ポジションスキーマが不正な場合にValueErrorが発生する"""

        class ConcreteCreator(BaseEntryOrderCreator):
            def create(
                self,
                portfolio_plan: pl.DataFrame,
                current_positions: pl.DataFrame,
                ohlcv: pl.DataFrame,
            ) -> pl.DataFrame:
                self._validate_inputs(portfolio_plan, current_positions, ohlcv)
                return pl.DataFrame()

        params = EntryOrderCreatorParams()
        creator = ConcreteCreator(params=params)

        portfolio_plan = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)],
                "symbol": ["AAPL"],
                "signal_strength": [1.5],
            }
        )
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
            creator.create(portfolio_plan, positions, ohlcv)

    def test_validate_inputs_invalid_ohlcv_schema(self) -> None:
        """OHLCVスキーマが不正な場合にValueErrorが発生する"""

        class ConcreteCreator(BaseEntryOrderCreator):
            def create(
                self,
                portfolio_plan: pl.DataFrame,
                current_positions: pl.DataFrame,
                ohlcv: pl.DataFrame,
            ) -> pl.DataFrame:
                self._validate_inputs(portfolio_plan, current_positions, ohlcv)
                return pl.DataFrame()

        params = EntryOrderCreatorParams()
        creator = ConcreteCreator(params=params)

        portfolio_plan = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)],
                "symbol": ["AAPL"],
                "signal_strength": [1.5],
            }
        )
        positions = pl.DataFrame(
            {"symbol": ["AAPL"], "quantity": [100.0], "avg_price": [150.0]}
        )
        # open列が欠けている
        ohlcv = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)],
                "symbol": ["AAPL"],
                "high": [155.0],
                "low": [148.0],
                "close": [153.0],
                "volume": [1000000],
            }
        )

        with pytest.raises(ValueError, match="必須列が不足しています"):
            creator.create(portfolio_plan, positions, ohlcv)


class TestBaseEntryOrderCreatorABC:
    """BaseEntryOrderCreatorのABC継承テスト"""

    def test_is_abstract_class(self) -> None:
        """BaseEntryOrderCreatorが抽象基底クラスであることを確認"""
        assert issubclass(BaseEntryOrderCreator, ABC)

    def test_cannot_instantiate_directly(self) -> None:
        """BaseEntryOrderCreatorは直接インスタンス化できない"""
        with pytest.raises(TypeError, match="abstract"):
            BaseEntryOrderCreator(params=EntryOrderCreatorParams())  # type: ignore

    def test_must_implement_create(self) -> None:
        """createメソッドの実装が必要"""

        # 抽象メソッドを実装しないサブクラス
        class IncompleteCreator(BaseEntryOrderCreator):
            pass

        with pytest.raises(TypeError, match="abstract"):
            IncompleteCreator(params=EntryOrderCreatorParams())  # type: ignore

    def test_subclass_with_create_works(self) -> None:
        """createメソッドを実装したサブクラスはインスタンス化できる"""

        class CompleteCreator(BaseEntryOrderCreator):
            def create(
                self,
                portfolio_plan: pl.DataFrame,
                current_positions: pl.DataFrame,
                ohlcv: pl.DataFrame,
            ) -> pl.DataFrame:
                return pl.DataFrame(
                    {
                        "symbol": ["TEST"],
                        "side": ["buy"],
                        "quantity": [100.0],
                        "price": [None],
                        "order_type": ["market"],
                    }
                )

        params = EntryOrderCreatorParams()
        creator = CompleteCreator(params=params)
        assert creator.params == params


class TestEqualWeightEntryOrderCreator:
    """EqualWeightEntryOrderCreatorのテスト"""

    def test_default_params(self) -> None:
        """デフォルトパラメータの確認"""
        from qeel.entry_order_creators.equal_weight import EqualWeightEntryParams

        params = EqualWeightEntryParams()
        assert params.capital == 1_000_000.0
        assert params.rebalance_threshold == 0.05

    def test_custom_params(self) -> None:
        """カスタムパラメータの確認"""
        from qeel.entry_order_creators.equal_weight import EqualWeightEntryParams

        params = EqualWeightEntryParams(capital=500_000.0, rebalance_threshold=0.1)
        assert params.capital == 500_000.0
        assert params.rebalance_threshold == 0.1

    def test_equal_weight_order_generation(self) -> None:
        """等ウェイトで注文が生成される"""
        from qeel.entry_order_creators.equal_weight import (
            EqualWeightEntryOrderCreator,
            EqualWeightEntryParams,
        )

        params = EqualWeightEntryParams(capital=1_000_000.0, rebalance_threshold=0.0)
        creator = EqualWeightEntryOrderCreator(params=params)

        portfolio_plan = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)] * 2,
                "symbol": ["AAPL", "GOOG"],
                "signal_strength": [1.5, 2.0],
            }
        )
        # ポジションなし
        positions = pl.DataFrame(
            {"symbol": [], "quantity": [], "avg_price": []},
            schema={
                "symbol": pl.String,
                "quantity": pl.Float64,
                "avg_price": pl.Float64,
            },
        )
        ohlcv = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)] * 2,
                "symbol": ["AAPL", "GOOG"],
                "open": [150.0, 100.0],
                "high": [155.0, 105.0],
                "low": [148.0, 98.0],
                "close": [153.0, 102.0],
                "volume": [1000000, 2000000],
            }
        )

        result = creator.create(portfolio_plan, positions, ohlcv)

        assert result.height == 2
        assert "symbol" in result.columns
        assert "side" in result.columns
        assert "quantity" in result.columns
        assert "order_type" in result.columns

        # すべて買い注文
        assert set(result["side"].to_list()) == {"buy"}
        # すべて成行注文
        assert set(result["order_type"].to_list()) == {"market"}

    def test_market_order_price_is_null(self) -> None:
        """成行注文のpriceはNone"""
        from qeel.entry_order_creators.equal_weight import (
            EqualWeightEntryOrderCreator,
            EqualWeightEntryParams,
        )

        params = EqualWeightEntryParams(capital=1_000_000.0, rebalance_threshold=0.0)
        creator = EqualWeightEntryOrderCreator(params=params)

        portfolio_plan = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)],
                "symbol": ["AAPL"],
                "signal_strength": [1.5],
            }
        )
        positions = pl.DataFrame(
            {"symbol": [], "quantity": [], "avg_price": []},
            schema={
                "symbol": pl.String,
                "quantity": pl.Float64,
                "avg_price": pl.Float64,
            },
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

        result = creator.create(portfolio_plan, positions, ohlcv)

        assert result["price"].null_count() == 1

    def test_negative_signal_generates_sell_order(self) -> None:
        """負のシグナルは売り注文を生成する"""
        from qeel.entry_order_creators.equal_weight import (
            EqualWeightEntryOrderCreator,
            EqualWeightEntryParams,
        )

        params = EqualWeightEntryParams(capital=1_000_000.0, rebalance_threshold=0.0)
        creator = EqualWeightEntryOrderCreator(params=params)

        portfolio_plan = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)] * 2,
                "symbol": ["AAPL", "GOOG"],
                "signal_strength": [1.5, -2.0],  # GOOGは負のシグナル
            }
        )
        positions = pl.DataFrame(
            {"symbol": [], "quantity": [], "avg_price": []},
            schema={
                "symbol": pl.String,
                "quantity": pl.Float64,
                "avg_price": pl.Float64,
            },
        )
        ohlcv = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)] * 2,
                "symbol": ["AAPL", "GOOG"],
                "open": [150.0, 100.0],
                "high": [155.0, 105.0],
                "low": [148.0, 98.0],
                "close": [153.0, 102.0],
                "volume": [1000000, 2000000],
            }
        )

        result = creator.create(portfolio_plan, positions, ohlcv)

        aapl_order = result.filter(pl.col("symbol") == "AAPL")
        goog_order = result.filter(pl.col("symbol") == "GOOG")

        assert aapl_order["side"][0] == "buy"
        assert goog_order["side"][0] == "sell"

    def test_empty_portfolio_returns_empty_dataframe(self) -> None:
        """空のポートフォリオに対して空のDataFrameを返す"""
        from qeel.entry_order_creators.equal_weight import (
            EqualWeightEntryOrderCreator,
            EqualWeightEntryParams,
        )

        params = EqualWeightEntryParams(capital=1_000_000.0)
        creator = EqualWeightEntryOrderCreator(params=params)

        portfolio_plan = pl.DataFrame(
            {"datetime": [], "symbol": [], "signal_strength": []},
            schema={
                "datetime": pl.Datetime,
                "symbol": pl.String,
                "signal_strength": pl.Float64,
            },
        )
        positions = pl.DataFrame(
            {"symbol": [], "quantity": [], "avg_price": []},
            schema={
                "symbol": pl.String,
                "quantity": pl.Float64,
                "avg_price": pl.Float64,
            },
        )
        ohlcv = pl.DataFrame(
            {
                "datetime": [],
                "symbol": [],
                "open": [],
                "high": [],
                "low": [],
                "close": [],
                "volume": [],
            },
            schema={
                "datetime": pl.Datetime,
                "symbol": pl.String,
                "open": pl.Float64,
                "high": pl.Float64,
                "low": pl.Float64,
                "close": pl.Float64,
                "volume": pl.Int64,
            },
        )

        result = creator.create(portfolio_plan, positions, ohlcv)

        assert result.height == 0

    def test_symbol_without_price_data_raises_error(self) -> None:
        """価格データがない銘柄があるとValueErrorが発生する"""
        import pytest

        from qeel.entry_order_creators.equal_weight import (
            EqualWeightEntryOrderCreator,
            EqualWeightEntryParams,
        )

        params = EqualWeightEntryParams(capital=1_000_000.0, rebalance_threshold=0.0)
        creator = EqualWeightEntryOrderCreator(params=params)

        portfolio_plan = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)] * 2,
                "symbol": ["AAPL", "GOOG"],
                "signal_strength": [1.5, 2.0],
            }
        )
        positions = pl.DataFrame(
            {"symbol": [], "quantity": [], "avg_price": []},
            schema={
                "symbol": pl.String,
                "quantity": pl.Float64,
                "avg_price": pl.Float64,
            },
        )
        # AAPLの価格データのみ（GOOGがない）
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

        with pytest.raises(ValueError, match="OHLCVデータが見つかりません"):
            creator.create(portfolio_plan, positions, ohlcv)

    def test_rebalance_threshold_skips_small_changes(self) -> None:
        """リバランス閾値以下の変動ではスキップされる"""
        from qeel.entry_order_creators.equal_weight import (
            EqualWeightEntryOrderCreator,
            EqualWeightEntryParams,
        )

        # リバランス閾値を50%に設定
        params = EqualWeightEntryParams(capital=1_000_000.0, rebalance_threshold=0.5)
        creator = EqualWeightEntryOrderCreator(params=params)

        portfolio_plan = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)],
                "symbol": ["AAPL"],
                "signal_strength": [1.5],
            }
        )
        # 既にほぼ目標ウェイトで保有している
        # 目標: 1,000,000 * 1.0 / 150 = 6666.67株
        # 現在: 6000株 * 150 = 900,000 = 90%ウェイト
        # 目標との差: |100% - 90%| = 10% < 50%閾値 → スキップ
        positions = pl.DataFrame(
            {"symbol": ["AAPL"], "quantity": [6000.0], "avg_price": [150.0]}
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

        result = creator.create(portfolio_plan, positions, ohlcv)

        # 閾値を超えていないのでスキップ
        assert result.height == 0

    def test_capital_param_validation(self) -> None:
        """capitalパラメータは正の値でなければならない"""
        from pydantic import ValidationError

        from qeel.entry_order_creators.equal_weight import EqualWeightEntryParams

        with pytest.raises(ValidationError):
            EqualWeightEntryParams(capital=0.0)

        with pytest.raises(ValidationError):
            EqualWeightEntryParams(capital=-1000.0)

    def test_rebalance_threshold_param_validation(self) -> None:
        """rebalance_thresholdパラメータは0-1の範囲でなければならない"""
        from pydantic import ValidationError

        from qeel.entry_order_creators.equal_weight import EqualWeightEntryParams

        with pytest.raises(ValidationError):
            EqualWeightEntryParams(rebalance_threshold=-0.1)

        with pytest.raises(ValidationError):
            EqualWeightEntryParams(rebalance_threshold=1.5)
