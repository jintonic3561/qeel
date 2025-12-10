"""取引所クライアント統合テスト

MockExchangeClientとMockDataSourceの連携テスト。
"""

from datetime import datetime

import polars as pl
import pytest

from qeel.config import CostConfig, DataSourceConfig
from qeel.data_sources.mock import MockDataSource
from qeel.exchange_clients.mock import MockExchangeClient


class TestMockExchangeClientIntegration:
    """MockExchangeClient統合テスト"""

    @pytest.fixture
    def sample_ohlcv_data(self) -> pl.DataFrame:
        """テスト用OHLCVデータ"""
        return pl.DataFrame(
            {
                "datetime": [
                    datetime(2024, 1, 1, 9, 0),
                    datetime(2024, 1, 2, 9, 0),
                    datetime(2024, 1, 3, 9, 0),
                    datetime(2024, 1, 4, 9, 0),
                    datetime(2024, 1, 5, 9, 0),
                    datetime(2024, 1, 1, 9, 0),
                    datetime(2024, 1, 2, 9, 0),
                    datetime(2024, 1, 3, 9, 0),
                    datetime(2024, 1, 4, 9, 0),
                    datetime(2024, 1, 5, 9, 0),
                ],
                "symbol": [
                    "AAPL",
                    "AAPL",
                    "AAPL",
                    "AAPL",
                    "AAPL",
                    "GOOGL",
                    "GOOGL",
                    "GOOGL",
                    "GOOGL",
                    "GOOGL",
                ],
                "open": [
                    100.0,
                    105.0,
                    110.0,
                    108.0,
                    112.0,
                    200.0,
                    210.0,
                    220.0,
                    215.0,
                    225.0,
                ],
                "high": [
                    108.0,
                    115.0,
                    118.0,
                    116.0,
                    120.0,
                    215.0,
                    225.0,
                    235.0,
                    230.0,
                    240.0,
                ],
                "low": [
                    98.0,
                    102.0,
                    105.0,
                    104.0,
                    108.0,
                    195.0,
                    205.0,
                    215.0,
                    210.0,
                    220.0,
                ],
                "close": [
                    105.0,
                    110.0,
                    115.0,
                    112.0,
                    118.0,
                    210.0,
                    220.0,
                    230.0,
                    225.0,
                    235.0,
                ],
                "volume": [
                    1000,
                    1100,
                    1200,
                    1150,
                    1250,
                    2000,
                    2100,
                    2200,
                    2150,
                    2250,
                ],
            }
        )

    @pytest.fixture
    def data_source_config(self) -> DataSourceConfig:
        """データソース設定"""
        return DataSourceConfig(
            name="ohlcv",
            datetime_column="datetime",
            offset_seconds=0,
            window_seconds=86400 * 30,
            module="qeel.data_sources.mock",
            class_name="MockDataSource",
            source_path="mock",
        )

    @pytest.fixture
    def cost_config(self) -> CostConfig:
        """コスト設定"""
        return CostConfig(
            commission_rate=0.001,
            slippage_bps=10.0,
        )

    def test_mock_exchange_client_full_workflow(
        self,
        sample_ohlcv_data: pl.DataFrame,
        data_source_config: DataSourceConfig,
        cost_config: CostConfig,
    ) -> None:
        """load_ohlcv → set_current_datetime → submit_orders → fetch_fills → fetch_positions の一連のフロー"""
        # セットアップ
        data_source = MockDataSource(config=data_source_config, data=sample_ohlcv_data)
        client = MockExchangeClient(cost_config, data_source)

        # 1. OHLCVデータをロード
        client.load_ohlcv(
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 10),
            symbols=["AAPL", "GOOGL"],
        )

        # 2. 日付を設定
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        # 3. 注文を実行
        orders = pl.DataFrame(
            {
                "symbol": ["AAPL", "GOOGL"],
                "side": ["buy", "buy"],
                "quantity": [10.0, 5.0],
                "price": [None, None],
                "order_type": ["market", "market"],
            }
        )
        client.submit_orders(orders)

        # 4. 約定を取得
        fills = client.fetch_fills(datetime(2024, 1, 1), datetime(2024, 1, 10))
        assert fills.height == 2
        assert set(fills["symbol"].to_list()) == {"AAPL", "GOOGL"}

        # 5. ポジションを確認
        positions = client.fetch_positions()
        assert positions.height == 2
        assert set(positions["symbol"].to_list()) == {"AAPL", "GOOGL"}

    def test_mock_exchange_client_multiple_iterations(
        self,
        sample_ohlcv_data: pl.DataFrame,
        data_source_config: DataSourceConfig,
        cost_config: CostConfig,
    ) -> None:
        """複数iterationでのポジション累積"""
        # セットアップ
        data_source = MockDataSource(config=data_source_config, data=sample_ohlcv_data)
        client = MockExchangeClient(cost_config, data_source)
        client.load_ohlcv(
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 10),
            symbols=["AAPL"],
        )

        # Iteration 1: 買い10株
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))
        orders1 = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["buy"],
                "quantity": [10.0],
                "price": [None],
                "order_type": ["market"],
            }
        )
        client.submit_orders(orders1)
        _ = client.fetch_fills(datetime(2024, 1, 1), datetime(2024, 1, 10))

        # Iteration 2: 買い追加5株
        client.set_current_datetime(datetime(2024, 1, 2, 9, 0))
        orders2 = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["buy"],
                "quantity": [5.0],
                "price": [None],
                "order_type": ["market"],
            }
        )
        client.submit_orders(orders2)
        _ = client.fetch_fills(datetime(2024, 1, 1), datetime(2024, 1, 10))

        # Iteration 3: 売り3株
        client.set_current_datetime(datetime(2024, 1, 3, 9, 0))
        orders3 = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["sell"],
                "quantity": [3.0],
                "price": [None],
                "order_type": ["market"],
            }
        )
        client.submit_orders(orders3)
        _ = client.fetch_fills(datetime(2024, 1, 1), datetime(2024, 1, 10))

        # 最終ポジション確認: 10 + 5 - 3 = 12株
        positions = client.fetch_positions()
        assert positions.height == 1
        assert positions["symbol"][0] == "AAPL"
        assert positions["quantity"][0] == pytest.approx(12.0, rel=1e-6)

    def test_mock_exchange_client_with_data_source(
        self,
        sample_ohlcv_data: pl.DataFrame,
        data_source_config: DataSourceConfig,
        cost_config: CostConfig,
    ) -> None:
        """DataSourceと連携したテスト"""
        # セットアップ
        data_source = MockDataSource(config=data_source_config, data=sample_ohlcv_data)
        client = MockExchangeClient(cost_config, data_source)

        # DataSourceからOHLCVをロード
        client.load_ohlcv(
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 10),
            symbols=["AAPL"],
        )

        assert client.ohlcv_cache is not None
        assert "AAPL" in client.ohlcv_cache["symbol"].to_list()

        # 成行注文を実行
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))
        orders = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["buy"],
                "quantity": [10.0],
                "price": [None],
                "order_type": ["market"],
            }
        )
        client.submit_orders(orders)

        fills = client.fetch_fills(datetime(2024, 1, 1), datetime(2024, 1, 10))
        assert fills.height == 1
        # 翌バー（1/2）のopen: 105.0 + slippage
        assert fills["filled_price"][0] > 105.0

        # 指値注文を実行
        client.set_current_datetime(datetime(2024, 1, 2, 9, 0))
        limit_orders = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["sell"],
                "quantity": [5.0],
                "price": [117.0],  # 翌バー(1/3)のhigh: 118.0 より低いので約定
                "order_type": ["limit"],
            }
        )
        client.submit_orders(limit_orders)

        # 指値注文の約定は翌バー（2024-01-03）で発生
        fills2 = client.fetch_fills(datetime(2024, 1, 3), datetime(2024, 1, 10))
        assert fills2.height == 1
        assert fills2["filled_price"][0] == 117.0

        # ポジション確認: 10 - 5 = 5株
        positions = client.fetch_positions()
        assert positions["quantity"][0] == pytest.approx(5.0, rel=1e-6)

    def test_mock_exchange_client_short_position(
        self,
        sample_ohlcv_data: pl.DataFrame,
        data_source_config: DataSourceConfig,
        cost_config: CostConfig,
    ) -> None:
        """ショートポジション（マイナス数量）のテスト"""
        # セットアップ
        data_source = MockDataSource(config=data_source_config, data=sample_ohlcv_data)
        client = MockExchangeClient(cost_config, data_source)
        client.load_ohlcv(
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 10),
            symbols=["AAPL"],
        )

        # 売りから入る（ショートポジション）
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))
        orders = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["sell"],
                "quantity": [10.0],
                "price": [None],
                "order_type": ["market"],
            }
        )
        client.submit_orders(orders)
        _ = client.fetch_fills(datetime(2024, 1, 1), datetime(2024, 1, 10))

        # ショートポジション確認: -10株
        positions = client.fetch_positions()
        assert positions.height == 1
        assert positions["symbol"][0] == "AAPL"
        assert positions["quantity"][0] == pytest.approx(-10.0, rel=1e-6)
        # 売りの加重平均価格
        assert positions["avg_price"][0] > 0

    def test_mock_exchange_client_position_close(
        self,
        sample_ohlcv_data: pl.DataFrame,
        data_source_config: DataSourceConfig,
        cost_config: CostConfig,
    ) -> None:
        """ポジションクローズのテスト"""
        # セットアップ
        data_source = MockDataSource(config=data_source_config, data=sample_ohlcv_data)
        client = MockExchangeClient(cost_config, data_source)
        client.load_ohlcv(
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 10),
            symbols=["AAPL"],
        )

        # 買いポジション
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))
        orders1 = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["buy"],
                "quantity": [10.0],
                "price": [None],
                "order_type": ["market"],
            }
        )
        client.submit_orders(orders1)
        _ = client.fetch_fills(datetime(2024, 1, 1), datetime(2024, 1, 10))

        # 全株売却
        client.set_current_datetime(datetime(2024, 1, 2, 9, 0))
        orders2 = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["sell"],
                "quantity": [10.0],
                "price": [None],
                "order_type": ["market"],
            }
        )
        client.submit_orders(orders2)
        _ = client.fetch_fills(datetime(2024, 1, 1), datetime(2024, 1, 10))

        # ポジションなし
        positions = client.fetch_positions()
        assert positions.height == 0
