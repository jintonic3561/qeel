"""IOレイヤーの統合テスト"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from qeel.config import GeneralConfig


class TestLocalIOIntegration:
    """LocalIOの統合テスト"""

    def test_local_io_with_config(self, tmp_path: Path) -> None:
        """GeneralConfig(storage_type='local')からLocalIOを取得し、save/load/list_filesが正常動作"""
        from qeel.io.base import BaseIO
        from qeel.io.local import LocalIO

        config = GeneralConfig(strategy_name="test_strategy", storage_type="local")

        with patch("qeel.io.local.get_workspace", return_value=tmp_path):
            io = BaseIO.from_config(config)

            assert isinstance(io, LocalIO)

            # save
            df = pl.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
            path = str(tmp_path / "data" / "test.parquet")
            io.save(path, df, format="parquet")

            # load
            loaded = io.load(path, format="parquet")
            assert isinstance(loaded, pl.DataFrame)
            assert loaded.shape == (3, 2)

            # list_files
            files = io.list_files(str(tmp_path / "data"))
            assert len(files) == 1


class TestContextStoreIntegration:
    """ContextStoreの統合テスト"""

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

    def test_context_store_with_local_io(self, tmp_path: Path, mock_exchange_client: MagicMock) -> None:
        """LocalIOを使用したContextStoreの動作確認"""
        from qeel.io.local import LocalIO
        from qeel.stores.context_store import ContextStore

        with patch("qeel.io.local.get_workspace", return_value=tmp_path):
            io = LocalIO()
            store = ContextStore(io)

            target_datetime = datetime(2025, 1, 15)

            # シグナルを保存
            signals = pl.DataFrame(
                {
                    "datetime": [target_datetime],
                    "symbol": ["AAPL"],
                    "signal": [0.5],
                }
            )
            store.save_signals(target_datetime, signals)

            # 読み込み
            ctx = store.load(target_datetime, mock_exchange_client)

            assert ctx is not None
            assert ctx.current_datetime == target_datetime
            assert ctx.signals is not None
            assert ctx.signals.shape[0] == 1

    def test_context_store_partition_workflow(self, tmp_path: Path, mock_exchange_client: MagicMock) -> None:
        """複数日付の保存・読み込みワークフロー"""
        from qeel.io.local import LocalIO
        from qeel.stores.context_store import ContextStore

        with patch("qeel.io.local.get_workspace", return_value=tmp_path):
            io = LocalIO()
            store = ContextStore(io)

            # 複数日付のデータを保存
            dates = [
                datetime(2025, 1, 10),
                datetime(2025, 1, 15),
                datetime(2025, 2, 5),
            ]

            for dt in dates:
                signals = pl.DataFrame({"datetime": [dt], "symbol": ["AAPL"], "signal": [0.5]})
                store.save_signals(dt, signals)

            # パーティションディレクトリが作成されていることを確認
            jan_dir = tmp_path / "outputs" / "context" / "2025" / "01"
            feb_dir = tmp_path / "outputs" / "context" / "2025" / "02"
            assert jan_dir.exists()
            assert feb_dir.exists()

            # 各日付で読み込み可能
            for dt in dates:
                ctx = store.load(dt, mock_exchange_client)
                assert ctx is not None
                assert ctx.current_datetime == dt

            # 最新を取得
            latest = store.load_latest(mock_exchange_client)
            assert latest is not None
            assert latest.current_datetime == datetime(2025, 2, 5)
