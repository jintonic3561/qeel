"""StrategyEngineの統合テスト"""

from __future__ import annotations

from datetime import datetime

import polars as pl
import pytest

from qeel.config import Config, CostConfig, DataSourceConfig, GeneralConfig, LoopConfig
from qeel.config.params import (
    EntryOrderCreatorParams,
    ExitOrderCreatorParams,
    PortfolioConstructorParams,
    SignalCalculatorParams,
)
from qeel.core.strategy_engine import StepName, StrategyEngine
from qeel.models.context import Context
from qeel.stores.in_memory import InMemoryStore

# テスト用のシンプルな実装クラス


class SimpleSignalCalculator:
    """シンプルなシグナル計算（テスト用）"""

    def __init__(self, params: SignalCalculatorParams | None = None) -> None:
        self.params = params

    def calculate(self, data_sources: dict[str, pl.DataFrame]) -> pl.DataFrame:
        """OHLCVから単純なシグナルを生成"""
        ohlcv = data_sources["ohlcv"]
        # 各銘柄の最新の行だけを取得し、シグナルとして返す
        latest = ohlcv.group_by("symbol").agg(
            [
                pl.col("datetime").max(),
                pl.col("close").last().alias("signal"),
            ]
        )
        return latest.with_columns(pl.col("datetime").cast(pl.Datetime))


class SimplePortfolioConstructor:
    """シンプルなポートフォリオ構築（テスト用）"""

    def __init__(self, params: PortfolioConstructorParams | None = None) -> None:
        self.params = params

    def construct(self, signals: pl.DataFrame, current_positions: pl.DataFrame) -> pl.DataFrame:
        """全シグナル銘柄をポートフォリオに含める"""
        return signals.select(["datetime", "symbol", "signal"]).rename({"signal": "signal_strength"})


class SimpleEntryOrderCreator:
    """シンプルなエントリー注文生成（テスト用）"""

    def __init__(self, params: EntryOrderCreatorParams | None = None) -> None:
        self.params = params

    def create(
        self,
        portfolio_plan: pl.DataFrame,
        current_positions: pl.DataFrame,
        ohlcv: pl.DataFrame,
    ) -> pl.DataFrame:
        """ポートフォリオ銘柄に対して買い注文を生成"""
        symbols = portfolio_plan["symbol"].to_list()

        if not symbols:
            return pl.DataFrame(
                {
                    "symbol": pl.Series([], dtype=pl.Utf8),
                    "side": pl.Series([], dtype=pl.Utf8),
                    "quantity": pl.Series([], dtype=pl.Float64),
                    "price": pl.Series([], dtype=pl.Float64),
                    "order_type": pl.Series([], dtype=pl.Utf8),
                }
            )

        return pl.DataFrame(
            {
                "symbol": symbols,
                "side": ["buy"] * len(symbols),
                "quantity": [10.0] * len(symbols),
                "price": [None] * len(symbols),
                "order_type": ["market"] * len(symbols),
            }
        )


class SimpleExitOrderCreator:
    """シンプルなエグジット注文生成（テスト用）"""

    def __init__(self, params: ExitOrderCreatorParams | None = None) -> None:
        self.params = params

    def create(self, current_positions: pl.DataFrame, ohlcv: pl.DataFrame) -> pl.DataFrame:
        """保有ポジションに対して売り注文を生成"""
        if current_positions.height == 0:
            return pl.DataFrame(
                {
                    "symbol": pl.Series([], dtype=pl.Utf8),
                    "side": pl.Series([], dtype=pl.Utf8),
                    "quantity": pl.Series([], dtype=pl.Float64),
                    "price": pl.Series([], dtype=pl.Float64),
                    "order_type": pl.Series([], dtype=pl.Utf8),
                }
            )

        # quantityが正の場合のみ決済
        positions_to_exit = current_positions.filter(pl.col("quantity") > 0)
        if positions_to_exit.height == 0:
            return pl.DataFrame(
                {
                    "symbol": pl.Series([], dtype=pl.Utf8),
                    "side": pl.Series([], dtype=pl.Utf8),
                    "quantity": pl.Series([], dtype=pl.Float64),
                    "price": pl.Series([], dtype=pl.Float64),
                    "order_type": pl.Series([], dtype=pl.Utf8),
                }
            )

        return pl.DataFrame(
            {
                "symbol": positions_to_exit["symbol"].to_list(),
                "side": ["sell"] * positions_to_exit.height,
                "quantity": positions_to_exit["quantity"].to_list(),
                "price": [None] * positions_to_exit.height,
                "order_type": ["market"] * positions_to_exit.height,
            }
        )


class SimpleDataSource:
    """シンプルなデータソース（テスト用）"""

    def __init__(self, data: pl.DataFrame) -> None:
        self.data = data
        self.config = type(
            "Config",
            (),
            {
                "name": "ohlcv",
                "datetime_column": "datetime",
                "offset_seconds": 0,
                "window_seconds": 86400 * 30,
            },
        )()

    def fetch(self, start: datetime, end: datetime, symbols: list[str]) -> pl.DataFrame:
        """指定期間・銘柄のデータを返す"""
        result = self.data.filter(
            (pl.col("datetime") >= start)
            & (pl.col("datetime") <= end)
            & (pl.col("symbol").is_in(symbols) if symbols else pl.lit(True))
        )
        return result


class SimpleExchangeClient:
    """シンプルな取引所クライアント（テスト用）"""

    def __init__(self) -> None:
        self.positions: dict[str, dict[str, float]] = {}
        self.fill_history: list[dict[str, object]] = []

    def fetch_positions(self) -> pl.DataFrame:
        """現在のポジションを返す"""
        if not self.positions:
            return pl.DataFrame(
                {
                    "symbol": pl.Series([], dtype=pl.Utf8),
                    "quantity": pl.Series([], dtype=pl.Float64),
                    "avg_price": pl.Series([], dtype=pl.Float64),
                }
            )

        return pl.DataFrame(
            {
                "symbol": list(self.positions.keys()),
                "quantity": [p["quantity"] for p in self.positions.values()],
                "avg_price": [p["avg_price"] for p in self.positions.values()],
            }
        )

    def submit_orders(self, orders: pl.DataFrame) -> None:
        """注文を処理してポジションを更新"""
        for row in orders.to_dicts():
            symbol = row["symbol"]
            side = row["side"]
            quantity = row["quantity"]

            if symbol not in self.positions:
                self.positions[symbol] = {"quantity": 0.0, "avg_price": 0.0}

            if side == "buy":
                self.positions[symbol]["quantity"] += quantity
                self.positions[symbol]["avg_price"] = 100.0  # ダミー価格
            else:  # sell
                self.positions[symbol]["quantity"] -= quantity

            self.fill_history.append(
                {
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                }
            )

            # quantityが0になったらポジションを削除
            if self.positions[symbol]["quantity"] == 0:
                del self.positions[symbol]


# フィクスチャ


@pytest.fixture
def sample_ohlcv_data() -> pl.DataFrame:
    """テスト用OHLCVデータ（2銘柄、3日分）"""
    data = []
    for day in range(1, 4):
        for symbol in ["AAPL", "GOOGL"]:
            data.append(
                {
                    "datetime": datetime(2024, 1, day),
                    "symbol": symbol,
                    "open": 100.0 + day,
                    "high": 105.0 + day,
                    "low": 99.0 + day,
                    "close": 104.0 + day,
                    "volume": 1000000,
                }
            )

    return pl.DataFrame(data).with_columns(pl.col("datetime").cast(pl.Datetime))


@pytest.fixture
def sample_config() -> Config:
    """テスト用Config"""
    return Config(
        general=GeneralConfig(
            strategy_name="test_strategy",
            storage_type="local",
        ),
        data_sources=[
            DataSourceConfig(
                name="ohlcv",
                datetime_column="datetime",
                offset_seconds=0,
                window_seconds=86400 * 30,
                module="tests.integration.test_strategy_engine_integration",
                class_name="SimpleDataSource",
                source_path="/tmp/test.parquet",
            )
        ],
        costs=CostConfig(),
        loop=LoopConfig(
            frequency="1d",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 3),
            universe=["AAPL", "GOOGL"],
        ),
    )


@pytest.fixture
def strategy_engine_with_simple_components(
    sample_ohlcv_data: pl.DataFrame,
    sample_config: Config,
) -> tuple[StrategyEngine, SimpleExchangeClient, InMemoryStore]:
    """シンプルなコンポーネントを使用したStrategyEngine"""
    data_source = SimpleDataSource(sample_ohlcv_data)
    exchange_client = SimpleExchangeClient()
    context_store = InMemoryStore()

    engine = StrategyEngine(
        config=sample_config,
        data_sources={"ohlcv": data_source},  # type: ignore
        signal_calculator=SimpleSignalCalculator(),  # type: ignore
        portfolio_constructor=SimplePortfolioConstructor(),  # type: ignore
        entry_order_creator=SimpleEntryOrderCreator(),  # type: ignore
        exit_order_creator=SimpleExitOrderCreator(),  # type: ignore
        exchange_client=exchange_client,  # type: ignore
        context_store=context_store,
    )

    return engine, exchange_client, context_store


class TestStrategyEngineE2E:
    """StrategyEngine E2Eテスト"""

    def test_run_all_steps_generates_signals_and_orders(
        self,
        strategy_engine_with_simple_components: tuple[StrategyEngine, SimpleExchangeClient, InMemoryStore],
    ) -> None:
        """run_all_stepsがシグナル・ポートフォリオ・注文を正しく生成すること"""
        engine, exchange_client, context_store = strategy_engine_with_simple_components
        target_date = datetime(2024, 1, 2)
        engine._context = Context(current_datetime=target_date)

        engine.run_all_steps(target_date)

        # Contextの各要素が設定されていること
        assert engine._context.signals is not None
        assert "datetime" in engine._context.signals.columns
        assert "symbol" in engine._context.signals.columns

        assert engine._context.portfolio_plan is not None
        assert "symbol" in engine._context.portfolio_plan.columns

        assert engine._context.entry_orders is not None
        assert engine._context.entry_orders.height > 0

        # 約定履歴に追加されていること
        assert len(exchange_client.fill_history) > 0

    def test_run_all_steps_updates_positions(
        self,
        strategy_engine_with_simple_components: tuple[StrategyEngine, SimpleExchangeClient, InMemoryStore],
    ) -> None:
        """run_all_stepsがポジションを正しく更新すること"""
        engine, exchange_client, context_store = strategy_engine_with_simple_components
        target_date = datetime(2024, 1, 2)
        engine._context = Context(current_datetime=target_date)

        engine.run_all_steps(target_date)

        # ポジションが作成されていること
        positions = exchange_client.fetch_positions()
        assert positions.height > 0


class TestStrategyEngineMultipleIterations:
    """StrategyEngine複数日連続実行テスト"""

    def test_multiple_iterations_accumulate_positions(
        self,
        strategy_engine_with_simple_components: tuple[StrategyEngine, SimpleExchangeClient, InMemoryStore],
    ) -> None:
        """複数日の実行でポジションが累積すること"""
        engine, exchange_client, context_store = strategy_engine_with_simple_components

        # Day 1
        day1 = datetime(2024, 1, 1)
        engine._context = Context(current_datetime=day1)
        engine.run_all_steps(day1)

        # Day 1終了時点でポジションが存在することを確認
        positions_after_day1 = exchange_client.fetch_positions()
        assert positions_after_day1.height > 0

        # Day 2 (エグジットしないので追加注文)
        day2 = datetime(2024, 1, 2)
        engine._context = Context(current_datetime=day2)
        engine.run_all_steps(day2)

        positions_after_day2 = exchange_client.fetch_positions()

        # ポジションが存在すること
        assert positions_after_day2.height > 0

        # 約定履歴に両日分が含まれていること
        assert len(exchange_client.fill_history) >= 2  # 少なくとも2回の注文


class TestStrategyEngineContextPersistence:
    """StrategyEngineコンテキスト永続化テスト"""

    def test_partial_execution_and_resume(
        self,
        strategy_engine_with_simple_components: tuple[StrategyEngine, SimpleExchangeClient, InMemoryStore],
        sample_ohlcv_data: pl.DataFrame,
        sample_config: Config,
    ) -> None:
        """部分実行後に新しいエンジンで再開できること"""
        engine, exchange_client, context_store = strategy_engine_with_simple_components
        target_date = datetime(2024, 1, 2)
        engine._context = Context(current_datetime=target_date)

        # 部分実行（シグナル計算とポートフォリオ構築のみ）
        engine.run_step(target_date, StepName.CALCULATE_SIGNALS)
        engine.run_step(target_date, StepName.CONSTRUCT_PORTFOLIO)

        # シグナルとポートフォリオが保存されていること
        assert engine._context.signals is not None
        assert engine._context.portfolio_plan is not None

        # 新しいエンジンを作成してコンテキストを復元
        data_source = SimpleDataSource(sample_ohlcv_data)
        new_engine = StrategyEngine(
            config=sample_config,
            data_sources={"ohlcv": data_source},  # type: ignore
            signal_calculator=SimpleSignalCalculator(),  # type: ignore
            portfolio_constructor=SimplePortfolioConstructor(),  # type: ignore
            entry_order_creator=SimpleEntryOrderCreator(),  # type: ignore
            exit_order_creator=SimpleExitOrderCreator(),  # type: ignore
            exchange_client=exchange_client,  # type: ignore
            context_store=context_store,  # 同じストアを使用
        )

        # コンテキストを復元
        restored_context = new_engine.load_context(target_date)

        # 復元されたコンテキストにシグナルとポートフォリオが含まれること
        assert restored_context.signals is not None
        assert restored_context.portfolio_plan is not None

        # 残りのステップを実行
        new_engine.run_step(target_date, StepName.CREATE_EXIT_ORDERS)
        new_engine.run_step(target_date, StepName.CREATE_ENTRY_ORDERS)
        new_engine.run_step(target_date, StepName.SUBMIT_EXIT_ORDERS)
        new_engine.run_step(target_date, StepName.SUBMIT_ENTRY_ORDERS)

        # 注文が実行されたこと
        assert len(exchange_client.fill_history) > 0

    def test_single_step_independent_execution(
        self,
        strategy_engine_with_simple_components: tuple[StrategyEngine, SimpleExchangeClient, InMemoryStore],
    ) -> None:
        """単一ステップを独立して実行できること（実運用想定）"""
        engine, exchange_client, context_store = strategy_engine_with_simple_components
        target_date = datetime(2024, 1, 2)

        # load_contextで新規コンテキストを作成
        engine.load_context(target_date)

        # calculate_signalsのみ実行
        engine.run_step(target_date, StepName.CALCULATE_SIGNALS)

        # signalsが設定され、他の要素はNoneのままであること
        assert engine._context is not None
        assert engine._context.signals is not None
        assert engine._context.portfolio_plan is None
        assert engine._context.entry_orders is None
        assert engine._context.exit_orders is None
