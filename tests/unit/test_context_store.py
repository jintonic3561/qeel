"""ContextStoreのテスト"""

from datetime import datetime
from unittest.mock import MagicMock

import polars as pl
import pytest

from qeel.io.in_memory import InMemoryIO


class TestContextStore:
    """ContextStoreのテスト"""

    @pytest.fixture
    def io(self) -> InMemoryIO:
        """テスト用InMemoryIO"""
        return InMemoryIO()

    @pytest.fixture
    def mock_exchange_client(self) -> MagicMock:
        """モックExchangeClient"""
        client = MagicMock()
        client.fetch_positions.return_value = pl.DataFrame(
            {
                "symbol": ["AAPL", "GOOGL"],
                "quantity": [100.0, 50.0],
                "avg_price": [150.0, 2800.0],
            }
        )
        return client

    def test_context_store_save_signals(self, io: InMemoryIO) -> None:
        """シグナルを日付パーティショニングで保存"""
        from qeel.stores.context_store import ContextStore

        store = ContextStore(io)
        target_datetime = datetime(2025, 1, 15)
        signals = pl.DataFrame(
            {
                "datetime": [target_datetime],
                "symbol": ["AAPL"],
                "signal": [0.5],
            }
        )

        store.save_signals(target_datetime, signals)

        # IOに保存されていることを確認
        expected_path = "memory://outputs/context/2025/01/signals_2025-01-15.parquet"
        assert io.exists(expected_path)

    def test_context_store_save_portfolio_plan(self, io: InMemoryIO) -> None:
        """ポートフォリオ計画を保存"""
        from qeel.stores.context_store import ContextStore

        store = ContextStore(io)
        target_datetime = datetime(2025, 1, 15)
        portfolio_plan = pl.DataFrame(
            {
                "datetime": [target_datetime],
                "symbol": ["AAPL"],
                "signal_strength": [0.8],
            }
        )

        store.save_portfolio_plan(target_datetime, portfolio_plan)

        expected_path = "memory://outputs/context/2025/01/portfolio_plan_2025-01-15.parquet"
        assert io.exists(expected_path)

    def test_context_store_save_entry_orders(self, io: InMemoryIO) -> None:
        """エントリー注文を保存"""
        from qeel.stores.context_store import ContextStore

        store = ContextStore(io)
        target_datetime = datetime(2025, 1, 15)
        entry_orders = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["buy"],
                "quantity": [100.0],
                "price": [150.0],
                "order_type": ["limit"],
            }
        )

        store.save_entry_orders(target_datetime, entry_orders)

        expected_path = "memory://outputs/context/2025/01/entry_orders_2025-01-15.parquet"
        assert io.exists(expected_path)

    def test_context_store_save_exit_orders(self, io: InMemoryIO) -> None:
        """エグジット注文を保存"""
        from qeel.stores.context_store import ContextStore

        store = ContextStore(io)
        target_datetime = datetime(2025, 1, 15)
        exit_orders = pl.DataFrame(
            {
                "symbol": ["GOOGL"],
                "side": ["sell"],
                "quantity": [50.0],
                "price": [2800.0],
                "order_type": ["market"],
            }
        )

        store.save_exit_orders(target_datetime, exit_orders)

        expected_path = "memory://outputs/context/2025/01/exit_orders_2025-01-15.parquet"
        assert io.exists(expected_path)

    def test_context_store_load_returns_context(self, io: InMemoryIO, mock_exchange_client: MagicMock) -> None:
        """指定日付のコンテキストを復元"""
        from qeel.stores.context_store import ContextStore

        store = ContextStore(io)
        target_datetime = datetime(2025, 1, 15)

        # データを保存
        signals = pl.DataFrame({"datetime": [target_datetime], "symbol": ["AAPL"], "signal": [0.5]})
        portfolio_plan = pl.DataFrame({"datetime": [target_datetime], "symbol": ["AAPL"], "signal_strength": [0.8]})
        store.save_signals(target_datetime, signals)
        store.save_portfolio_plan(target_datetime, portfolio_plan)

        # 読み込み
        ctx = store.load(target_datetime, mock_exchange_client)

        assert ctx is not None
        assert ctx.current_datetime == target_datetime
        assert ctx.signals is not None
        assert ctx.signals.shape[0] == 1
        assert ctx.portfolio_plan is not None
        assert ctx.current_positions is not None

    def test_context_store_load_returns_none_when_not_exists(
        self, io: InMemoryIO, mock_exchange_client: MagicMock
    ) -> None:
        """保存された要素がない場合None"""
        from qeel.stores.context_store import ContextStore

        store = ContextStore(io)
        target_datetime = datetime(2025, 1, 15)

        ctx = store.load(target_datetime, mock_exchange_client)

        assert ctx is None

    def test_context_store_load_partial_elements(self, io: InMemoryIO, mock_exchange_client: MagicMock) -> None:
        """一部の要素のみ存在する場合も正常に復元"""
        from qeel.stores.context_store import ContextStore

        store = ContextStore(io)
        target_datetime = datetime(2025, 1, 15)

        # signalsのみ保存
        signals = pl.DataFrame({"datetime": [target_datetime], "symbol": ["AAPL"], "signal": [0.5]})
        store.save_signals(target_datetime, signals)

        # 読み込み
        ctx = store.load(target_datetime, mock_exchange_client)

        assert ctx is not None
        assert ctx.signals is not None
        assert ctx.portfolio_plan is None
        assert ctx.entry_orders is None
        assert ctx.exit_orders is None
        assert ctx.current_positions is not None

    def test_context_store_load_latest_returns_most_recent(
        self, io: InMemoryIO, mock_exchange_client: MagicMock
    ) -> None:
        """最新日付のコンテキストを復元"""
        from qeel.stores.context_store import ContextStore

        store = ContextStore(io)

        # 複数日付のデータを保存
        for day in [10, 15, 20]:
            dt = datetime(2025, 1, day)
            signals = pl.DataFrame({"datetime": [dt], "symbol": ["AAPL"], "signal": [day / 100]})
            store.save_signals(dt, signals)

        # 最新を読み込み
        ctx = store.load_latest(mock_exchange_client)

        assert ctx is not None
        assert ctx.current_datetime == datetime(2025, 1, 20)

    def test_context_store_load_latest_returns_none_when_empty(
        self, io: InMemoryIO, mock_exchange_client: MagicMock
    ) -> None:
        """保存データがない場合None"""
        from qeel.stores.context_store import ContextStore

        store = ContextStore(io)

        ctx = store.load_latest(mock_exchange_client)

        assert ctx is None

    def test_context_store_exists_returns_true(self, io: InMemoryIO) -> None:
        """コンテキストが存在する場合True"""
        from qeel.stores.context_store import ContextStore

        store = ContextStore(io)
        target_datetime = datetime(2025, 1, 15)

        signals = pl.DataFrame({"datetime": [target_datetime], "symbol": ["AAPL"], "signal": [0.5]})
        store.save_signals(target_datetime, signals)

        assert store.exists(target_datetime) is True

    def test_context_store_exists_returns_false(self, io: InMemoryIO) -> None:
        """コンテキストが存在しない場合False"""
        from qeel.stores.context_store import ContextStore

        store = ContextStore(io)
        target_datetime = datetime(2025, 1, 15)

        assert store.exists(target_datetime) is False

    def test_context_store_partition_directory_format(self, io: InMemoryIO) -> None:
        """年月パーティション形式（YYYY/MM/）の確認"""
        from qeel.stores.context_store import ContextStore

        store = ContextStore(io)

        # 異なる月のデータを保存
        jan = datetime(2025, 1, 15)
        feb = datetime(2025, 2, 20)

        store.save_signals(jan, pl.DataFrame({"datetime": [jan], "symbol": ["AAPL"], "signal": [0.5]}))
        store.save_signals(feb, pl.DataFrame({"datetime": [feb], "symbol": ["AAPL"], "signal": [0.6]}))

        # パーティションディレクトリが正しいことを確認
        jan_path = "memory://outputs/context/2025/01/signals_2025-01-15.parquet"
        feb_path = "memory://outputs/context/2025/02/signals_2025-02-20.parquet"

        assert io.exists(jan_path)
        assert io.exists(feb_path)


class TestInMemoryStore:
    """InMemoryStoreのテスト"""

    @pytest.fixture
    def mock_exchange_client(self) -> MagicMock:
        """モックExchangeClient"""
        client = MagicMock()
        client.fetch_positions.return_value = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "quantity": [100.0],
                "avg_price": [150.0],
            }
        )
        return client

    def test_in_memory_store_save_and_load(self, mock_exchange_client: MagicMock) -> None:
        """最新コンテキストのみ保持"""
        from qeel.stores.in_memory import InMemoryStore

        store = InMemoryStore()
        target_datetime = datetime(2025, 1, 15)

        signals = pl.DataFrame({"datetime": [target_datetime], "symbol": ["AAPL"], "signal": [0.5]})
        store.save_signals(target_datetime, signals)

        ctx = store.load(target_datetime, mock_exchange_client)

        assert ctx is not None
        assert ctx.signals is not None

    def test_in_memory_store_overwrites_previous(self, mock_exchange_client: MagicMock) -> None:
        """上書き動作の確認"""
        from qeel.stores.in_memory import InMemoryStore

        store = InMemoryStore()

        # 最初のデータ
        dt1 = datetime(2025, 1, 10)
        signals1 = pl.DataFrame({"datetime": [dt1], "symbol": ["AAPL"], "signal": [0.3]})
        store.save_signals(dt1, signals1)

        # 上書き
        dt2 = datetime(2025, 1, 15)
        signals2 = pl.DataFrame({"datetime": [dt2], "symbol": ["GOOGL"], "signal": [0.7]})
        store.save_signals(dt2, signals2)

        # 最新のみ保持されている
        ctx = store.load_latest(mock_exchange_client)
        assert ctx is not None
        assert ctx.current_datetime == dt2
        assert ctx.signals is not None
        assert ctx.signals["symbol"][0] == "GOOGL"

    def test_in_memory_store_load_latest(self, mock_exchange_client: MagicMock) -> None:
        """load_latestが最新を返す"""
        from qeel.stores.in_memory import InMemoryStore

        store = InMemoryStore()
        target_datetime = datetime(2025, 1, 15)

        signals = pl.DataFrame({"datetime": [target_datetime], "symbol": ["AAPL"], "signal": [0.5]})
        store.save_signals(target_datetime, signals)

        ctx = store.load_latest(mock_exchange_client)

        assert ctx is not None
        assert ctx.current_datetime == target_datetime

    def test_in_memory_store_exists(self) -> None:
        """存在確認"""
        from qeel.stores.in_memory import InMemoryStore

        store = InMemoryStore()

        assert store.exists(datetime(2025, 1, 15)) is False

        store.save_signals(
            datetime(2025, 1, 15),
            pl.DataFrame({"datetime": [datetime(2025, 1, 15)], "symbol": ["AAPL"], "signal": [0.5]}),
        )

        assert store.exists(datetime(2025, 1, 15)) is True
