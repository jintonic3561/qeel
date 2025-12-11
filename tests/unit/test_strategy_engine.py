"""StrategyEngineの単体テスト"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import polars as pl
import pytest

from qeel.core.strategy_engine import StepName

if TYPE_CHECKING:
    from qeel.calculators.signals.base import BaseSignalCalculator
    from qeel.config import Config
    from qeel.core.strategy_engine import StrategyEngine
    from qeel.data_sources.base import BaseDataSource
    from qeel.entry_order_creators.base import BaseEntryOrderCreator
    from qeel.exchange_clients.base import BaseExchangeClient
    from qeel.exit_order_creators.base import BaseExitOrderCreator
    from qeel.portfolio_constructors.base import BasePortfolioConstructor
    from qeel.stores.in_memory import InMemoryStore


# テスト用モッククラス


class MockSignalCalculator:
    """テスト用シグナル計算モック"""

    def __init__(self) -> None:
        self.params = None
        self.call_count = 0
        self.last_data_sources: dict[str, pl.DataFrame] | None = None

    def calculate(self, data_sources: dict[str, pl.DataFrame]) -> pl.DataFrame:
        self.call_count += 1
        self.last_data_sources = data_sources
        # SignalSchema準拠のDataFrameを返す
        return pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)],
                "symbol": ["AAPL"],
                "signal": [1.0],
            }
        ).with_columns(pl.col("datetime").cast(pl.Datetime))


class MockPortfolioConstructor:
    """テスト用ポートフォリオ構築モック"""

    def __init__(self) -> None:
        self.params = None
        self.call_count = 0
        self.last_signals: pl.DataFrame | None = None
        self.last_positions: pl.DataFrame | None = None

    def construct(self, signals: pl.DataFrame, current_positions: pl.DataFrame) -> pl.DataFrame:
        self.call_count += 1
        self.last_signals = signals
        self.last_positions = current_positions
        # PortfolioSchema準拠のDataFrameを返す
        return pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)],
                "symbol": ["AAPL"],
                "signal_strength": [1.0],
            }
        ).with_columns(pl.col("datetime").cast(pl.Datetime))


class MockEntryOrderCreator:
    """テスト用エントリー注文生成モック"""

    def __init__(self) -> None:
        self.params = None
        self.call_count = 0
        self.last_portfolio_plan: pl.DataFrame | None = None
        self.last_positions: pl.DataFrame | None = None
        self.last_ohlcv: pl.DataFrame | None = None

    def create(
        self,
        portfolio_plan: pl.DataFrame,
        current_positions: pl.DataFrame,
        ohlcv: pl.DataFrame,
    ) -> pl.DataFrame:
        self.call_count += 1
        self.last_portfolio_plan = portfolio_plan
        self.last_positions = current_positions
        self.last_ohlcv = ohlcv
        # OrderSchema準拠のDataFrameを返す
        return pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["buy"],
                "quantity": [10.0],
                "price": [None],
                "order_type": ["market"],
            }
        )


class MockExitOrderCreator:
    """テスト用エグジット注文生成モック"""

    def __init__(self) -> None:
        self.params = None
        self.call_count = 0
        self.last_positions: pl.DataFrame | None = None
        self.last_ohlcv: pl.DataFrame | None = None

    def create(
        self,
        current_positions: pl.DataFrame,
        ohlcv: pl.DataFrame,
    ) -> pl.DataFrame:
        self.call_count += 1
        self.last_positions = current_positions
        self.last_ohlcv = ohlcv
        # OrderSchema準拠のDataFrameを返す（空の場合）
        return pl.DataFrame(
            {
                "symbol": pl.Series([], dtype=pl.Utf8),
                "side": pl.Series([], dtype=pl.Utf8),
                "quantity": pl.Series([], dtype=pl.Float64),
                "price": pl.Series([], dtype=pl.Float64),
                "order_type": pl.Series([], dtype=pl.Utf8),
            }
        )


class MockExchangeClient:
    """テスト用取引所クライアントモック"""

    def __init__(self) -> None:
        self.submit_count = 0
        self.last_orders: pl.DataFrame | None = None
        self.positions = pl.DataFrame(
            {
                "symbol": pl.Series([], dtype=pl.Utf8),
                "quantity": pl.Series([], dtype=pl.Float64),
                "avg_price": pl.Series([], dtype=pl.Float64),
            }
        )

    def fetch_positions(self) -> pl.DataFrame:
        return self.positions

    def submit_orders(self, orders: pl.DataFrame) -> None:
        self.submit_count += 1
        self.last_orders = orders

    def fetch_fills(self, start: datetime, end: datetime) -> pl.DataFrame:
        return pl.DataFrame(
            schema={
                "order_id": pl.Utf8,
                "symbol": pl.Utf8,
                "side": pl.Utf8,
                "filled_quantity": pl.Float64,
                "filled_price": pl.Float64,
                "commission": pl.Float64,
                "timestamp": pl.Datetime,
            }
        )


class MockDataSource:
    """テスト用データソースモック"""

    def __init__(self, name: str = "ohlcv") -> None:
        self.config = type(
            "Config",
            (),
            {
                "name": name,
                "datetime_column": "datetime",
                "offset_seconds": 0,
                "window_seconds": 86400 * 30,  # 30日
            },
        )()
        self.call_count = 0
        self.last_start: datetime | None = None
        self.last_end: datetime | None = None
        self.last_symbols: list[str] | None = None

    def fetch(self, start: datetime, end: datetime, symbols: list[str]) -> pl.DataFrame:
        self.call_count += 1
        self.last_start = start
        self.last_end = end
        self.last_symbols = symbols
        # OHLCVSchema準拠のDataFrameを返す
        return pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1), datetime(2024, 1, 2)],
                "symbol": ["AAPL", "AAPL"],
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [104.0, 105.0],
                "volume": [1000000, 1100000],
            }
        ).with_columns(pl.col("datetime").cast(pl.Datetime))


# フィクスチャ


@pytest.fixture
def sample_config() -> "Config":
    """テスト用Config"""
    from qeel.config import Config, CostConfig, DataSourceConfig, GeneralConfig, LoopConfig

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
                window_seconds=86400 * 30,  # 30日
                module="qeel.data_sources.parquet",
                class_name="ParquetDataSource",
                source_path="/tmp/ohlcv.parquet",
            )
        ],
        costs=CostConfig(),
        loop=LoopConfig(
            frequency="1d",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            universe=["AAPL", "GOOGL"],
        ),
    )


@pytest.fixture
def mock_data_sources() -> dict[str, MockDataSource]:
    """テスト用データソース辞書"""
    return {"ohlcv": MockDataSource("ohlcv")}


@pytest.fixture
def mock_signal_calculator() -> MockSignalCalculator:
    """テスト用シグナル計算"""
    return MockSignalCalculator()


@pytest.fixture
def mock_portfolio_constructor() -> MockPortfolioConstructor:
    """テスト用ポートフォリオ構築"""
    return MockPortfolioConstructor()


@pytest.fixture
def mock_entry_order_creator() -> MockEntryOrderCreator:
    """テスト用エントリー注文生成"""
    return MockEntryOrderCreator()


@pytest.fixture
def mock_exit_order_creator() -> MockExitOrderCreator:
    """テスト用エグジット注文生成"""
    return MockExitOrderCreator()


@pytest.fixture
def mock_exchange_client() -> MockExchangeClient:
    """テスト用取引所クライアント"""
    return MockExchangeClient()


@pytest.fixture
def in_memory_store() -> "InMemoryStore":
    """テスト用インメモリストア"""
    from qeel.stores.in_memory import InMemoryStore

    return InMemoryStore()


@pytest.fixture
def strategy_engine(
    sample_config: "Config",
    mock_data_sources: dict[str, MockDataSource],
    mock_signal_calculator: MockSignalCalculator,
    mock_portfolio_constructor: MockPortfolioConstructor,
    mock_entry_order_creator: MockEntryOrderCreator,
    mock_exit_order_creator: MockExitOrderCreator,
    mock_exchange_client: MockExchangeClient,
    in_memory_store: "InMemoryStore",
) -> "StrategyEngine":
    """テスト用StrategyEngine"""
    from qeel.core.strategy_engine import StrategyEngine

    return StrategyEngine(
        config=sample_config,
        data_sources=mock_data_sources,
        signal_calculator=mock_signal_calculator,
        portfolio_constructor=mock_portfolio_constructor,
        entry_order_creator=mock_entry_order_creator,
        exit_order_creator=mock_exit_order_creator,
        exchange_client=mock_exchange_client,
        context_store=in_memory_store,
    )


class TestStepNameEnum:
    """StepName Enumのテスト"""

    def test_step_name_values_exist(self) -> None:
        """全てのステップ名が定義されていること"""
        assert StepName.CALCULATE_SIGNALS.value == "calculate_signals"
        assert StepName.CONSTRUCT_PORTFOLIO.value == "construct_portfolio"
        assert StepName.CREATE_ENTRY_ORDERS.value == "create_entry_orders"
        assert StepName.CREATE_EXIT_ORDERS.value == "create_exit_orders"
        assert StepName.SUBMIT_ENTRY_ORDERS.value == "submit_entry_orders"
        assert StepName.SUBMIT_EXIT_ORDERS.value == "submit_exit_orders"

    def test_step_name_string_conversion(self) -> None:
        """Enumの値から文字列を取得できること"""
        assert str(StepName.CALCULATE_SIGNALS.value) == "calculate_signals"
        assert str(StepName.CONSTRUCT_PORTFOLIO.value) == "construct_portfolio"

    def test_step_name_iteration(self) -> None:
        """全ステップをイテレートできること"""
        step_names = list(StepName)
        assert len(step_names) == 6


class TestStrategyEngineInit:
    """StrategyEngine初期化のテスト"""

    def test_strategy_engine_init_with_all_components(
        self,
        sample_config: "Config",
        mock_data_sources: dict[str, "BaseDataSource"],
        mock_signal_calculator: "BaseSignalCalculator",
        mock_portfolio_constructor: "BasePortfolioConstructor",
        mock_entry_order_creator: "BaseEntryOrderCreator",
        mock_exit_order_creator: "BaseExitOrderCreator",
        mock_exchange_client: "BaseExchangeClient",
        in_memory_store: "InMemoryStore",
    ) -> None:
        """全コンポーネントを受け取って初期化できること"""
        from qeel.core.strategy_engine import StrategyEngine

        engine = StrategyEngine(
            config=sample_config,
            data_sources=mock_data_sources,
            signal_calculator=mock_signal_calculator,
            portfolio_constructor=mock_portfolio_constructor,
            entry_order_creator=mock_entry_order_creator,
            exit_order_creator=mock_exit_order_creator,
            exchange_client=mock_exchange_client,
            context_store=in_memory_store,
        )

        # 各コンポーネントがプロパティとしてアクセス可能
        assert engine.config is sample_config
        assert engine.data_sources is mock_data_sources
        assert engine.signal_calculator is mock_signal_calculator
        assert engine.portfolio_constructor is mock_portfolio_constructor
        assert engine.entry_order_creator is mock_entry_order_creator
        assert engine.exit_order_creator is mock_exit_order_creator
        assert engine.exchange_client is mock_exchange_client
        assert engine.context_store is in_memory_store

    def test_strategy_engine_context_is_none_after_init(
        self,
        sample_config: "Config",
        mock_data_sources: dict[str, "BaseDataSource"],
        mock_signal_calculator: "BaseSignalCalculator",
        mock_portfolio_constructor: "BasePortfolioConstructor",
        mock_entry_order_creator: "BaseEntryOrderCreator",
        mock_exit_order_creator: "BaseExitOrderCreator",
        mock_exchange_client: "BaseExchangeClient",
        in_memory_store: "InMemoryStore",
    ) -> None:
        """初期化直後は_contextがNoneであること"""
        from qeel.core.strategy_engine import StrategyEngine

        engine = StrategyEngine(
            config=sample_config,
            data_sources=mock_data_sources,
            signal_calculator=mock_signal_calculator,
            portfolio_constructor=mock_portfolio_constructor,
            entry_order_creator=mock_entry_order_creator,
            exit_order_creator=mock_exit_order_creator,
            exchange_client=mock_exchange_client,
            context_store=in_memory_store,
        )

        assert engine._context is None


class TestStrategyEngineSteps:
    """StrategyEngine各ステップ実行のテスト"""

    def test_run_step_calculate_signals(
        self,
        strategy_engine: "StrategyEngine",
        mock_signal_calculator: MockSignalCalculator,
        mock_data_sources: dict[str, MockDataSource],
    ) -> None:
        """calculate_signalsステップが正しく動作すること"""
        from qeel.models.context import Context

        target_date = datetime(2024, 1, 15)
        strategy_engine._context = Context(current_datetime=target_date)

        strategy_engine.run_step(target_date, StepName.CALCULATE_SIGNALS)

        # signal_calculator.calculate()が呼ばれたこと
        assert mock_signal_calculator.call_count == 1
        assert mock_signal_calculator.last_data_sources is not None

        # Contextのsignalsが更新されたこと
        assert strategy_engine._context.signals is not None
        assert "datetime" in strategy_engine._context.signals.columns
        assert "symbol" in strategy_engine._context.signals.columns

    def test_run_step_construct_portfolio(
        self,
        strategy_engine: "StrategyEngine",
        mock_portfolio_constructor: MockPortfolioConstructor,
        mock_exchange_client: MockExchangeClient,
        in_memory_store: "InMemoryStore",
    ) -> None:
        """construct_portfolioステップが正しく動作すること"""
        target_date = datetime(2024, 1, 15)

        # 前提: signalsがストアに保存済み
        signals = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 15)],
                "symbol": ["AAPL"],
                "signal": [1.0],
            }
        ).with_columns(pl.col("datetime").cast(pl.Datetime))
        in_memory_store.save_signals(target_date, signals)

        strategy_engine.run_step(target_date, StepName.CONSTRUCT_PORTFOLIO)

        # portfolio_constructor.construct()が呼ばれたこと
        assert mock_portfolio_constructor.call_count == 1
        assert mock_portfolio_constructor.last_signals is not None
        assert mock_portfolio_constructor.last_positions is not None

        # Contextのportfolio_planが更新されたこと
        assert strategy_engine._context is not None
        assert strategy_engine._context.portfolio_plan is not None

    def test_run_step_create_entry_orders(
        self,
        strategy_engine: "StrategyEngine",
        mock_entry_order_creator: MockEntryOrderCreator,
        in_memory_store: "InMemoryStore",
    ) -> None:
        """create_entry_ordersステップが正しく動作すること"""
        target_date = datetime(2024, 1, 15)

        # 前提: portfolio_planがストアに保存済み
        portfolio_plan = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 15)],
                "symbol": ["AAPL"],
                "signal_strength": [1.0],
            }
        ).with_columns(pl.col("datetime").cast(pl.Datetime))
        in_memory_store.save_portfolio_plan(target_date, portfolio_plan)

        strategy_engine.run_step(target_date, StepName.CREATE_ENTRY_ORDERS)

        # entry_order_creator.create()が呼ばれたこと
        assert mock_entry_order_creator.call_count == 1
        assert mock_entry_order_creator.last_portfolio_plan is not None
        assert mock_entry_order_creator.last_ohlcv is not None

        # Contextのentry_ordersが更新されたこと
        assert strategy_engine._context is not None
        assert strategy_engine._context.entry_orders is not None

    def test_run_step_create_exit_orders(
        self,
        strategy_engine: "StrategyEngine",
        mock_exit_order_creator: MockExitOrderCreator,
        mock_exchange_client: MockExchangeClient,
    ) -> None:
        """create_exit_ordersステップが正しく動作すること"""
        from qeel.models.context import Context

        target_date = datetime(2024, 1, 15)
        strategy_engine._context = Context(current_datetime=target_date)

        strategy_engine.run_step(target_date, StepName.CREATE_EXIT_ORDERS)

        # exit_order_creator.create()が呼ばれたこと
        assert mock_exit_order_creator.call_count == 1
        assert mock_exit_order_creator.last_positions is not None
        assert mock_exit_order_creator.last_ohlcv is not None

        # Contextのexit_ordersが更新されたこと
        assert strategy_engine._context.exit_orders is not None

    def test_run_step_submit_entry_orders(
        self,
        strategy_engine: "StrategyEngine",
        mock_exchange_client: MockExchangeClient,
        in_memory_store: "InMemoryStore",
    ) -> None:
        """submit_entry_ordersステップが正しく動作すること"""
        target_date = datetime(2024, 1, 15)

        # 前提: entry_ordersがストアに保存済み
        entry_orders = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["buy"],
                "quantity": [10.0],
                "price": [None],
                "order_type": ["market"],
            }
        )
        in_memory_store.save_entry_orders(target_date, entry_orders)

        strategy_engine.run_step(target_date, StepName.SUBMIT_ENTRY_ORDERS)

        # exchange_client.submit_orders()が呼ばれたこと
        assert mock_exchange_client.submit_count == 1
        assert mock_exchange_client.last_orders is not None

    def test_run_step_submit_entry_orders_skips_empty(
        self,
        strategy_engine: "StrategyEngine",
        mock_exchange_client: MockExchangeClient,
        in_memory_store: "InMemoryStore",
    ) -> None:
        """空のentry_ordersの場合、submit_ordersが呼ばれないこと"""
        target_date = datetime(2024, 1, 15)

        # 空のentry_ordersをストアに保存
        entry_orders = pl.DataFrame(
            {
                "symbol": pl.Series([], dtype=pl.Utf8),
                "side": pl.Series([], dtype=pl.Utf8),
                "quantity": pl.Series([], dtype=pl.Float64),
                "price": pl.Series([], dtype=pl.Float64),
                "order_type": pl.Series([], dtype=pl.Utf8),
            }
        )
        in_memory_store.save_entry_orders(target_date, entry_orders)

        strategy_engine.run_step(target_date, StepName.SUBMIT_ENTRY_ORDERS)

        # submit_ordersは呼ばれない
        assert mock_exchange_client.submit_count == 0

    def test_run_step_submit_exit_orders(
        self,
        strategy_engine: "StrategyEngine",
        mock_exchange_client: MockExchangeClient,
        in_memory_store: "InMemoryStore",
    ) -> None:
        """submit_exit_ordersステップが正しく動作すること"""
        target_date = datetime(2024, 1, 15)

        # 前提: exit_ordersがストアに保存済み
        exit_orders = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["sell"],
                "quantity": [10.0],
                "price": [None],
                "order_type": ["market"],
            }
        )
        in_memory_store.save_exit_orders(target_date, exit_orders)

        strategy_engine.run_step(target_date, StepName.SUBMIT_EXIT_ORDERS)

        # exchange_client.submit_orders()が呼ばれたこと
        assert mock_exchange_client.submit_count == 1


class TestStrategyEngineRunMethods:
    """StrategyEngine run_step/run_stepsのテスト"""

    def test_run_step_dispatches_to_correct_method(
        self,
        strategy_engine: "StrategyEngine",
        mock_signal_calculator: MockSignalCalculator,
    ) -> None:
        """run_stepが正しいメソッドにディスパッチすること"""
        from qeel.models.context import Context

        target_date = datetime(2024, 1, 15)
        strategy_engine._context = Context(current_datetime=target_date)

        strategy_engine.run_step(target_date, StepName.CALCULATE_SIGNALS)
        assert mock_signal_calculator.call_count == 1

    def test_run_step_invalid_step_raises_value_error(
        self,
        strategy_engine: "StrategyEngine",
    ) -> None:
        """不正なステップ名でValueErrorが発生すること"""
        from qeel.models.context import Context

        target_date = datetime(2024, 1, 15)
        strategy_engine._context = Context(current_datetime=target_date)

        with pytest.raises(ValueError, match="不正なステップ名"):
            strategy_engine.run_step(target_date, "invalid_step")  # type: ignore

    def test_run_step_sets_current_datetime(
        self,
        strategy_engine: "StrategyEngine",
    ) -> None:
        """run_stepがContextのcurrent_datetimeを設定すること"""
        from qeel.models.context import Context

        target_date = datetime(2024, 1, 15)
        strategy_engine._context = Context(current_datetime=datetime(2024, 1, 1))

        strategy_engine.run_step(target_date, StepName.CALCULATE_SIGNALS)

        assert strategy_engine._context.current_datetime == target_date

    def test_run_steps_executes_multiple_steps(
        self,
        strategy_engine: "StrategyEngine",
        mock_signal_calculator: MockSignalCalculator,
        mock_portfolio_constructor: MockPortfolioConstructor,
    ) -> None:
        """run_stepsが複数ステップを順番に実行すること"""
        from qeel.models.context import Context

        target_date = datetime(2024, 1, 15)
        strategy_engine._context = Context(current_datetime=target_date)

        strategy_engine.run_steps(
            target_date,
            [StepName.CALCULATE_SIGNALS, StepName.CONSTRUCT_PORTFOLIO],
        )

        assert mock_signal_calculator.call_count == 1
        assert mock_portfolio_constructor.call_count == 1

    def test_run_steps_empty_list_does_nothing(
        self,
        strategy_engine: "StrategyEngine",
        mock_signal_calculator: MockSignalCalculator,
    ) -> None:
        """空のリストを渡した場合は何も実行しないこと"""
        target_date = datetime(2024, 1, 15)

        strategy_engine.run_steps(target_date, [])

        assert mock_signal_calculator.call_count == 0

    def test_run_step_auto_loads_context(
        self,
        strategy_engine: "StrategyEngine",
        mock_signal_calculator: MockSignalCalculator,
    ) -> None:
        """run_stepが自動的にcontextをロードすること"""
        target_date = datetime(2024, 1, 15)

        # _contextがNoneの状態からrun_stepを呼ぶ
        assert strategy_engine._context is None

        strategy_engine.run_step(target_date, StepName.CALCULATE_SIGNALS)

        # contextが自動的にロードされていること
        assert strategy_engine._context is not None
        assert strategy_engine._context.current_datetime == target_date

    def test_run_step_always_reloads_context(
        self,
        strategy_engine: "StrategyEngine",
        in_memory_store: "InMemoryStore",
        mock_signal_calculator: MockSignalCalculator,
    ) -> None:
        """run_stepが毎回contextをリロードすること（最新状態を保証）"""
        target_date = datetime(2024, 1, 15)

        # 最初のステップ実行
        strategy_engine.run_step(target_date, StepName.CALCULATE_SIGNALS)
        first_context = strategy_engine._context

        # signalsが保存されていることを確認
        assert first_context is not None
        assert first_context.signals is not None

        # 新しいエンジンインスタンスを作成（別のスケジューラ呼び出しを模擬）
        from qeel.core.strategy_engine import StrategyEngine

        new_engine = StrategyEngine(
            config=strategy_engine.config,
            data_sources=strategy_engine.data_sources,
            signal_calculator=strategy_engine.signal_calculator,
            portfolio_constructor=strategy_engine.portfolio_constructor,
            entry_order_creator=strategy_engine.entry_order_creator,
            exit_order_creator=strategy_engine.exit_order_creator,
            exchange_client=strategy_engine.exchange_client,
            context_store=in_memory_store,
        )

        # 次のステップを実行 - 前のステップのsignalsが自動的にロードされる
        new_engine.run_step(target_date, StepName.CONSTRUCT_PORTFOLIO)

        # signalsがロードされていること
        assert new_engine._context is not None
        assert new_engine._context.signals is not None


class TestStrategyEngineDataFetch:
    """StrategyEngineデータ取得のテスト"""

    def test_get_data_fetch_range_basic(
        self,
        strategy_engine: "StrategyEngine",
    ) -> None:
        """_get_data_fetch_rangeが正しい期間を返すこと"""
        from qeel.config import DataSourceConfig

        target_date = datetime(2024, 1, 15)
        ds_config = DataSourceConfig(
            name="ohlcv",
            datetime_column="datetime",
            offset_seconds=0,
            window_seconds=86400 * 30,  # 30日
            module="qeel.data_sources.parquet",
            class_name="ParquetDataSource",
            source_path="/tmp/ohlcv.parquet",
        )

        start, end = strategy_engine._get_data_fetch_range(target_date, ds_config)

        # end = target_date - offset(0)
        assert end == target_date
        # start = end - window(30日)
        assert start == datetime(2023, 12, 16)

    def test_get_data_fetch_range_with_offset(
        self,
        strategy_engine: "StrategyEngine",
    ) -> None:
        """offset_secondsが正しく適用されること"""
        from qeel.config import DataSourceConfig

        target_date = datetime(2024, 1, 15, 12, 0, 0)
        ds_config = DataSourceConfig(
            name="ohlcv",
            datetime_column="datetime",
            offset_seconds=3600,  # 1時間オフセット
            window_seconds=86400,  # 1日
            module="qeel.data_sources.parquet",
            class_name="ParquetDataSource",
            source_path="/tmp/ohlcv.parquet",
        )

        start, end = strategy_engine._get_data_fetch_range(target_date, ds_config)

        # end = target_date - offset(1時間)
        assert end == datetime(2024, 1, 15, 11, 0, 0)
        # start = end - window(1日)
        assert start == datetime(2024, 1, 14, 11, 0, 0)


class TestStrategyEngineContextRestore:
    """StrategyEngineコンテキスト復元のテスト"""

    def test_load_context_with_date(
        self,
        strategy_engine: "StrategyEngine",
        in_memory_store: "InMemoryStore",
        mock_exchange_client: MockExchangeClient,
    ) -> None:
        """load_context(date)で指定日付のコンテキストを復元できること"""
        # InMemoryStoreにデータを保存
        target_date = datetime(2024, 1, 15)
        signals = pl.DataFrame(
            {
                "datetime": [target_date],
                "symbol": ["AAPL"],
                "signal": [1.0],
            }
        ).with_columns(pl.col("datetime").cast(pl.Datetime))
        in_memory_store.save_signals(target_date, signals)

        # load_contextで復元
        context = strategy_engine.load_context(target_date)

        assert context is not None
        assert strategy_engine._context is context
        assert context.signals is not None

    def test_load_context_without_date_loads_latest(
        self,
        strategy_engine: "StrategyEngine",
        in_memory_store: "InMemoryStore",
        mock_exchange_client: MockExchangeClient,
    ) -> None:
        """load_context()（引数なし）で最新コンテキストを復元できること"""
        # InMemoryStoreにデータを保存
        target_date = datetime(2024, 1, 15)
        signals = pl.DataFrame(
            {
                "datetime": [target_date],
                "symbol": ["AAPL"],
                "signal": [1.0],
            }
        ).with_columns(pl.col("datetime").cast(pl.Datetime))
        in_memory_store.save_signals(target_date, signals)

        # load_context()で復元
        context = strategy_engine.load_context()

        assert context is not None
        assert strategy_engine._context is context

    def test_load_context_creates_new_if_not_exists(
        self,
        strategy_engine: "StrategyEngine",
    ) -> None:
        """コンテキストが存在しない場合は新規Contextを作成すること"""
        target_date = datetime(2024, 1, 15)

        context = strategy_engine.load_context(target_date)

        assert context is not None
        assert context.current_datetime == target_date
        assert context.signals is None
        assert context.portfolio_plan is None


class TestStrategyEngineErrorHandling:
    """StrategyEngineエラーハンドリングのテスト"""

    def test_strategy_engine_error_on_data_fetch_failure(
        self,
        sample_config: "Config",
        mock_signal_calculator: MockSignalCalculator,
        mock_portfolio_constructor: MockPortfolioConstructor,
        mock_entry_order_creator: MockEntryOrderCreator,
        mock_exit_order_creator: MockExitOrderCreator,
        mock_exchange_client: MockExchangeClient,
        in_memory_store: "InMemoryStore",
    ) -> None:
        """データ取得失敗時にStrategyEngineErrorが発生すること"""
        from qeel.core.strategy_engine import StrategyEngine, StrategyEngineError
        from qeel.models.context import Context

        # 失敗するデータソースを作成
        class FailingDataSource:
            def __init__(self) -> None:
                self.config = type(
                    "Config",
                    (),
                    {
                        "name": "ohlcv",
                        "datetime_column": "datetime",
                        "offset_seconds": 0,
                        "window_seconds": 86400,
                    },
                )()

            def fetch(self, start: datetime, end: datetime, symbols: list[str]) -> pl.DataFrame:
                raise RuntimeError("データ取得に失敗しました")

        engine = StrategyEngine(
            config=sample_config,
            data_sources={"ohlcv": FailingDataSource()},  # type: ignore
            signal_calculator=mock_signal_calculator,
            portfolio_constructor=mock_portfolio_constructor,
            entry_order_creator=mock_entry_order_creator,
            exit_order_creator=mock_exit_order_creator,
            exchange_client=mock_exchange_client,
            context_store=in_memory_store,
        )

        target_date = datetime(2024, 1, 15)
        engine._context = Context(current_datetime=target_date)

        with pytest.raises(StrategyEngineError) as exc_info:
            engine.run_step(target_date, StepName.CALCULATE_SIGNALS)

        assert exc_info.value.step_name == StepName.CALCULATE_SIGNALS
        assert exc_info.value.target_date == target_date
        assert "calculate_signals" in str(exc_info.value)

    def test_strategy_engine_error_on_signal_calculation_failure(
        self,
        sample_config: "Config",
        mock_data_sources: dict[str, MockDataSource],
        mock_portfolio_constructor: MockPortfolioConstructor,
        mock_entry_order_creator: MockEntryOrderCreator,
        mock_exit_order_creator: MockExitOrderCreator,
        mock_exchange_client: MockExchangeClient,
        in_memory_store: "InMemoryStore",
    ) -> None:
        """シグナル計算失敗時にStrategyEngineErrorが発生すること"""
        from qeel.core.strategy_engine import StrategyEngine, StrategyEngineError
        from qeel.models.context import Context

        # 失敗するシグナル計算を作成
        class FailingSignalCalculator:
            def __init__(self) -> None:
                self.params = None

            def calculate(self, data_sources: dict[str, pl.DataFrame]) -> pl.DataFrame:
                raise ValueError("シグナル計算に失敗しました")

        engine = StrategyEngine(
            config=sample_config,
            data_sources=mock_data_sources,
            signal_calculator=FailingSignalCalculator(),  # type: ignore
            portfolio_constructor=mock_portfolio_constructor,
            entry_order_creator=mock_entry_order_creator,
            exit_order_creator=mock_exit_order_creator,
            exchange_client=mock_exchange_client,
            context_store=in_memory_store,
        )

        target_date = datetime(2024, 1, 15)
        engine._context = Context(current_datetime=target_date)

        with pytest.raises(StrategyEngineError) as exc_info:
            engine.run_step(target_date, StepName.CALCULATE_SIGNALS)

        assert exc_info.value.step_name == StepName.CALCULATE_SIGNALS
        assert "シグナル計算に失敗" in str(exc_info.value.original_error)

    def test_strategy_engine_error_contains_debug_info(
        self,
        sample_config: "Config",
        mock_data_sources: dict[str, MockDataSource],
        mock_signal_calculator: MockSignalCalculator,
        mock_portfolio_constructor: MockPortfolioConstructor,
        mock_entry_order_creator: MockEntryOrderCreator,
        mock_exit_order_creator: MockExitOrderCreator,
        mock_exchange_client: MockExchangeClient,
        in_memory_store: "InMemoryStore",
    ) -> None:
        """StrategyEngineErrorにデバッグ情報が含まれること"""
        from qeel.core.strategy_engine import StrategyEngineError

        original = ValueError("original error")
        error = StrategyEngineError(
            message="テストエラー",
            step_name=StepName.CALCULATE_SIGNALS,
            target_date=datetime(2024, 1, 15),
            original_error=original,
        )

        assert error.step_name == StepName.CALCULATE_SIGNALS
        assert error.target_date == datetime(2024, 1, 15)
        assert error.original_error is original
        assert "テストエラー" in str(error)
        assert "calculate_signals" in str(error)
        assert "2024-01-15" in str(error)
