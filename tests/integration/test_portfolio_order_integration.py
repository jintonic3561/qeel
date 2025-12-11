"""ポートフォリオ構築と注文生成の統合テスト

TopNPortfolioConstructor → EqualWeightEntryOrderCreator のフロー確認
TopNPortfolioConstructor → FullExitOrderCreator のフロー確認
signal_strengthメタデータがエントリー注文生成で正しく参照されることを確認
"""

from datetime import datetime

import polars as pl
import pytest


class TestPortfolioToEntryOrderFlow:
    """TopNPortfolioConstructor → EqualWeightEntryOrderCreator のフロー確認"""

    def test_portfolio_to_entry_order_basic_flow(self) -> None:
        """基本的なフロー: ポートフォリオ構築 → エントリー注文生成"""
        from qeel.entry_order_creators.equal_weight import (
            EqualWeightEntryOrderCreator,
            EqualWeightEntryParams,
        )
        from qeel.portfolio_constructors.top_n import (
            TopNConstructorParams,
            TopNPortfolioConstructor,
        )

        # シグナルデータ
        signals = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)] * 5,
                "symbol": ["AAPL", "GOOGL", "MSFT", "AMZN", "NVDA"],
                "signal": [0.9, 0.8, 0.7, 0.6, 0.5],
            }
        )
        current_positions = pl.DataFrame(
            {
                "symbol": pl.Series([], dtype=pl.String),
                "quantity": pl.Series([], dtype=pl.Float64),
                "avg_price": pl.Series([], dtype=pl.Float64),
            }
        )

        # ポートフォリオ構築: 上位3銘柄を選定
        portfolio_params = TopNConstructorParams(top_n=3)
        portfolio_constructor = TopNPortfolioConstructor(params=portfolio_params)
        portfolio = portfolio_constructor.construct(signals, current_positions)

        # ポートフォリオの検証
        assert portfolio.height == 3
        assert set(portfolio["symbol"].to_list()) == {"AAPL", "GOOGL", "MSFT"}
        assert "signal_strength" in portfolio.columns

        # OHLCVデータ
        ohlcv = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)] * 3,
                "symbol": ["AAPL", "GOOGL", "MSFT"],
                "open": [150.0, 2500.0, 350.0],
                "high": [155.0, 2550.0, 355.0],
                "low": [148.0, 2480.0, 345.0],
                "close": [153.0, 2520.0, 352.0],
                "volume": [1000000, 500000, 800000],
            }
        )

        # エントリー注文生成
        entry_params = EqualWeightEntryParams(capital=1_000_000.0, rebalance_threshold=0.0)
        entry_creator = EqualWeightEntryOrderCreator(params=entry_params)
        orders = entry_creator.create(portfolio, current_positions, ohlcv)

        # 注文の検証
        assert orders.height == 3
        assert set(orders["symbol"].to_list()) == {"AAPL", "GOOGL", "MSFT"}
        assert all(side == "buy" for side in orders["side"].to_list())
        assert all(ot == "market" for ot in orders["order_type"].to_list())
        assert all(price is None for price in orders["price"].to_list())

    def test_signal_strength_used_for_side_determination(self) -> None:
        """signal_strengthを参照して買い/売りを決定することを確認"""
        from qeel.entry_order_creators.equal_weight import (
            EqualWeightEntryOrderCreator,
            EqualWeightEntryParams,
        )
        from qeel.portfolio_constructors.top_n import (
            TopNConstructorParams,
            TopNPortfolioConstructor,
        )

        # 正と負のシグナルを含むデータ
        signals = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)] * 4,
                "symbol": ["AAPL", "GOOGL", "MSFT", "AMZN"],
                "signal": [0.9, -0.8, 0.7, -0.6],  # 絶対値でソート
            }
        )
        current_positions = pl.DataFrame(
            {
                "symbol": pl.Series([], dtype=pl.String),
                "quantity": pl.Series([], dtype=pl.Float64),
                "avg_price": pl.Series([], dtype=pl.Float64),
            }
        )

        # ポートフォリオ構築: 上位2銘柄を選定（シグナル大きい順 = 0.9, 0.7）
        portfolio_params = TopNConstructorParams(top_n=2)
        portfolio_constructor = TopNPortfolioConstructor(params=portfolio_params)
        portfolio = portfolio_constructor.construct(signals, current_positions)

        assert portfolio.height == 2
        # signal降順なので、AAPL (0.9)、MSFT (0.7)が選ばれる
        assert set(portfolio["symbol"].to_list()) == {"AAPL", "MSFT"}

        ohlcv = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)] * 2,
                "symbol": ["AAPL", "MSFT"],
                "open": [150.0, 350.0],
                "high": [155.0, 355.0],
                "low": [148.0, 345.0],
                "close": [153.0, 352.0],
                "volume": [1000000, 800000],
            }
        )

        entry_params = EqualWeightEntryParams(capital=1_000_000.0, rebalance_threshold=0.0)
        entry_creator = EqualWeightEntryOrderCreator(params=entry_params)
        orders = entry_creator.create(portfolio, current_positions, ohlcv)

        # 正のシグナル強度 → 買い
        for row in orders.iter_rows(named=True):
            symbol = row["symbol"]
            side = row["side"]
            signal_row = portfolio.filter(pl.col("symbol") == symbol)
            signal_strength = signal_row["signal_strength"][0]
            if signal_strength > 0:
                assert side == "buy", f"{symbol}: positive signal should result in buy"
            else:
                assert side == "sell", f"{symbol}: negative signal should result in sell"


class TestPortfolioToExitOrderFlow:
    """TopNPortfolioConstructor → FullExitOrderCreator のフロー確認"""

    def test_portfolio_to_exit_order_basic_flow(self) -> None:
        """基本的なフロー: ポジションから全決済注文生成"""
        from qeel.exit_order_creators.full_exit import (
            FullExitOrderCreator,
            FullExitParams,
        )

        # 現在のポジション
        current_positions = pl.DataFrame(
            {
                "symbol": ["AAPL", "GOOGL"],
                "quantity": [100.0, 50.0],
                "avg_price": [150.0, 2500.0],
            }
        )

        ohlcv = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)] * 2,
                "symbol": ["AAPL", "GOOGL"],
                "open": [150.0, 2500.0],
                "high": [155.0, 2550.0],
                "low": [148.0, 2480.0],
                "close": [153.0, 2520.0],
                "volume": [1000000, 500000],
            }
        )

        # 全決済注文生成
        exit_params = FullExitParams(exit_threshold=1.0)
        exit_creator = FullExitOrderCreator(params=exit_params)
        orders = exit_creator.create(current_positions, ohlcv)

        # 注文の検証
        assert orders.height == 2
        assert set(orders["symbol"].to_list()) == {"AAPL", "GOOGL"}
        assert all(side == "sell" for side in orders["side"].to_list())
        assert all(ot == "market" for ot in orders["order_type"].to_list())

    def test_partial_exit_with_threshold(self) -> None:
        """exit_thresholdを使用した部分決済"""
        from qeel.exit_order_creators.full_exit import (
            FullExitOrderCreator,
            FullExitParams,
        )

        current_positions = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "quantity": [100.0],
                "avg_price": [150.0],
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

        # 50%決済
        exit_params = FullExitParams(exit_threshold=0.5)
        exit_creator = FullExitOrderCreator(params=exit_params)
        orders = exit_creator.create(current_positions, ohlcv)

        assert orders.height == 1
        assert orders["quantity"][0] == pytest.approx(50.0)


class TestCompleteWorkflow:
    """ポートフォリオ構築からエントリー/エグジットまでの完全なフロー"""

    def test_complete_entry_and_exit_workflow(self) -> None:
        """完全なワークフロー: シグナル → ポートフォリオ → エントリー → エグジット"""
        from qeel.entry_order_creators.equal_weight import (
            EqualWeightEntryOrderCreator,
            EqualWeightEntryParams,
        )
        from qeel.exit_order_creators.full_exit import (
            FullExitOrderCreator,
            FullExitParams,
        )
        from qeel.portfolio_constructors.top_n import (
            TopNConstructorParams,
            TopNPortfolioConstructor,
        )

        # Step 1: シグナル計算結果
        signals = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)] * 5,
                "symbol": ["AAPL", "GOOGL", "MSFT", "AMZN", "NVDA"],
                "signal": [0.9, 0.8, 0.7, 0.6, 0.5],
            }
        )

        # Step 2: ポートフォリオ構築（上位3銘柄）
        portfolio_params = TopNConstructorParams(top_n=3)
        portfolio_constructor = TopNPortfolioConstructor(params=portfolio_params)
        empty_positions = pl.DataFrame(
            {
                "symbol": pl.Series([], dtype=pl.String),
                "quantity": pl.Series([], dtype=pl.Float64),
                "avg_price": pl.Series([], dtype=pl.Float64),
            }
        )
        portfolio = portfolio_constructor.construct(signals, empty_positions)

        assert portfolio.height == 3
        assert "signal_strength" in portfolio.columns

        # Step 3: エントリー注文生成
        ohlcv = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)] * 3,
                "symbol": ["AAPL", "GOOGL", "MSFT"],
                "open": [150.0, 2500.0, 350.0],
                "high": [155.0, 2550.0, 355.0],
                "low": [148.0, 2480.0, 345.0],
                "close": [153.0, 2520.0, 352.0],
                "volume": [1000000, 500000, 800000],
            }
        )

        entry_params = EqualWeightEntryParams(capital=1_000_000.0, rebalance_threshold=0.0)
        entry_creator = EqualWeightEntryOrderCreator(params=entry_params)
        entry_orders = entry_creator.create(portfolio, empty_positions, ohlcv)

        assert entry_orders.height == 3
        assert all(side == "buy" for side in entry_orders["side"].to_list())

        # Step 4: ポジションを持っている状態をシミュレート
        # 等ウェイトで3銘柄、1銘柄あたり333,333円相当
        current_positions = pl.DataFrame(
            {
                "symbol": ["AAPL", "GOOGL", "MSFT"],
                "quantity": [2222.22, 133.33, 952.38],  # capital/3/price
                "avg_price": [150.0, 2500.0, 350.0],
            }
        )

        # Step 5: エグジット注文生成（全決済）
        exit_params = FullExitParams(exit_threshold=1.0)
        exit_creator = FullExitOrderCreator(params=exit_params)
        exit_orders = exit_creator.create(current_positions, ohlcv)

        assert exit_orders.height == 3
        assert all(side == "sell" for side in exit_orders["side"].to_list())
        # 注文数量がポジション数量と一致することを確認
        for symbol in ["AAPL", "GOOGL", "MSFT"]:
            position_qty = current_positions.filter(pl.col("symbol") == symbol)["quantity"][0]
            order_qty = exit_orders.filter(pl.col("symbol") == symbol)["quantity"][0]
            assert order_qty == pytest.approx(position_qty, rel=0.01)
