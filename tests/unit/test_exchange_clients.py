"""取引所クライアントのユニットテスト"""

from abc import ABC
from datetime import datetime
from unittest.mock import MagicMock

import polars as pl
import pytest

from qeel.config import CostConfig
from qeel.data_sources.base import BaseDataSource


class TestBaseExchangeClient:
    """BaseExchangeClient ABCのテスト"""

    def test_base_exchange_client_cannot_instantiate(self) -> None:
        """ABCは直接インスタンス化できない"""
        from qeel.exchange_clients.base import BaseExchangeClient

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            BaseExchangeClient()  # type: ignore[abstract]

    def test_base_exchange_client_has_abstract_methods(self) -> None:
        """submit_orders, fetch_fills, fetch_positionsが抽象メソッドである"""
        from qeel.exchange_clients.base import BaseExchangeClient

        # ABCから継承した抽象メソッドを確認
        assert hasattr(BaseExchangeClient, "submit_orders")
        assert hasattr(BaseExchangeClient, "fetch_fills")
        assert hasattr(BaseExchangeClient, "fetch_positions")

        # 抽象メソッドであることを確認
        abstract_methods = BaseExchangeClient.__abstractmethods__
        assert "submit_orders" in abstract_methods
        assert "fetch_fills" in abstract_methods
        assert "fetch_positions" in abstract_methods

    def test_base_exchange_client_is_abc(self) -> None:
        """BaseExchangeClientはABCを継承している"""
        from qeel.exchange_clients.base import BaseExchangeClient

        assert issubclass(BaseExchangeClient, ABC)

    def test_base_exchange_client_has_validation_helpers(self) -> None:
        """バリデーションヘルパーメソッドが存在する"""
        from qeel.exchange_clients.base import BaseExchangeClient

        assert hasattr(BaseExchangeClient, "_validate_orders")
        assert hasattr(BaseExchangeClient, "_validate_fills")
        assert hasattr(BaseExchangeClient, "_validate_positions")


# テスト用OHLCVデータのフィクスチャ
@pytest.fixture
def sample_ohlcv_data() -> pl.DataFrame:
    """テスト用OHLCVデータ"""
    return pl.DataFrame(
        {
            "datetime": [
                datetime(2024, 1, 1, 9, 0),
                datetime(2024, 1, 2, 9, 0),
                datetime(2024, 1, 3, 9, 0),
                datetime(2024, 1, 1, 9, 0),
                datetime(2024, 1, 2, 9, 0),
                datetime(2024, 1, 3, 9, 0),
            ],
            "symbol": ["AAPL", "AAPL", "AAPL", "GOOGL", "GOOGL", "GOOGL"],
            "open": [100.0, 105.0, 110.0, 200.0, 210.0, 220.0],
            "high": [108.0, 115.0, 118.0, 215.0, 225.0, 235.0],
            "low": [98.0, 102.0, 105.0, 195.0, 205.0, 215.0],
            "close": [105.0, 110.0, 115.0, 210.0, 220.0, 230.0],
            "volume": [1000, 1100, 1200, 2000, 2100, 2200],
        }
    )


@pytest.fixture
def mock_data_source(sample_ohlcv_data: pl.DataFrame) -> MagicMock:
    """モックデータソース"""
    mock = MagicMock(spec=BaseDataSource)
    mock.fetch.return_value = sample_ohlcv_data
    return mock


@pytest.fixture
def cost_config() -> CostConfig:
    """コスト設定"""
    return CostConfig(
        commission_rate=0.001,  # 0.1%
        slippage_bps=10.0,  # 10bps
    )


class TestMockExchangeClientBase:
    """MockExchangeClient基盤のテスト"""

    def test_mock_exchange_client_init(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """MockExchangeClientが正常に初期化される"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)

        assert client.config == cost_config
        assert client.ohlcv_data_source == mock_data_source
        assert client.ohlcv_cache is None
        assert client.current_datetime is None
        assert client.fill_history == []

    def test_mock_exchange_client_init_stores_data_source(
        self, cost_config: CostConfig, mock_data_source: MagicMock
    ) -> None:
        """ohlcv_data_source属性にBaseDataSourceインスタンスが保持される"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)

        assert client.ohlcv_data_source is mock_data_source

    def test_mock_exchange_client_load_ohlcv(
        self,
        cost_config: CostConfig,
        mock_data_source: MagicMock,
        sample_ohlcv_data: pl.DataFrame,
    ) -> None:
        """OHLCVデータをキャッシュする"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)

        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 3)
        symbols = ["AAPL", "GOOGL"]

        client.load_ohlcv(start, end, symbols)

        assert client.ohlcv_cache is not None
        assert client.ohlcv_cache.height == sample_ohlcv_data.height

    def test_mock_exchange_client_load_ohlcv_calls_fetch(
        self, cost_config: CostConfig, mock_data_source: MagicMock
    ) -> None:
        """load_ohlcv()がBaseDataSource.fetch()を呼び出す"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)

        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 3)
        symbols = ["AAPL", "GOOGL"]

        client.load_ohlcv(start, end, symbols)

        mock_data_source.fetch.assert_called_once_with(start, end, symbols)

    def test_mock_exchange_client_set_current_datetime(
        self, cost_config: CostConfig, mock_data_source: MagicMock
    ) -> None:
        """現在のiteration日時を設定する"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        dt = datetime(2024, 1, 2)

        client.set_current_datetime(dt)

        assert client.current_datetime == dt

    def test_mock_exchange_client_get_next_bar(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """翌バーのOHLCVを取得する"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)

        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 5)
        symbols = ["AAPL", "GOOGL"]

        client.load_ohlcv(start, end, symbols)
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        next_bar = client._get_next_bar("AAPL")

        assert next_bar is not None
        assert next_bar.height == 1
        assert next_bar["datetime"][0] == datetime(2024, 1, 2, 9, 0)
        assert next_bar["open"][0] == 105.0

    def test_mock_exchange_client_get_current_bar(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """当バーのOHLCVを取得する"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)

        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 5)
        symbols = ["AAPL", "GOOGL"]

        client.load_ohlcv(start, end, symbols)
        client.set_current_datetime(datetime(2024, 1, 2, 9, 0))

        current_bar = client._get_current_bar("AAPL")

        assert current_bar is not None
        assert current_bar.height == 1
        assert current_bar["datetime"][0] == datetime(2024, 1, 2, 9, 0)
        assert current_bar["close"][0] == 110.0


class TestMockExchangeClientSlippage:
    """MockExchangeClientスリッページ計算のテスト"""

    def test_apply_slippage_buy_increases_price(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """買い注文でスリッページ適用後、価格が上昇する"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)

        base_price = 100.0
        slipped_price = client._apply_slippage(base_price, "buy")

        # 10bps = 0.1% なので、100 * 1.001 = 100.1
        assert slipped_price > base_price
        assert slipped_price == pytest.approx(100.1, rel=1e-6)

    def test_apply_slippage_sell_decreases_price(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """売り注文でスリッページ適用後、価格が下落する"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)

        base_price = 100.0
        slipped_price = client._apply_slippage(base_price, "sell")

        # 10bps = 0.1% なので、100 * 0.999 = 99.9
        assert slipped_price < base_price
        assert slipped_price == pytest.approx(99.9, rel=1e-6)

    def test_apply_slippage_zero_bps_no_change(self, mock_data_source: MagicMock) -> None:
        """スリッページ0bpsの場合、価格変化なし"""
        from qeel.exchange_clients.mock import MockExchangeClient

        zero_slippage_config = CostConfig(slippage_bps=0.0)
        client = MockExchangeClient(zero_slippage_config, mock_data_source)

        base_price = 100.0

        buy_price = client._apply_slippage(base_price, "buy")
        sell_price = client._apply_slippage(base_price, "sell")

        assert buy_price == base_price
        assert sell_price == base_price

    def test_apply_slippage_calculation_formula(self, mock_data_source: MagicMock) -> None:
        """計算式が正しい（price * (1 ± slippage_bps/10000)）"""
        from qeel.exchange_clients.mock import MockExchangeClient

        # 50bps = 0.5%
        config = CostConfig(slippage_bps=50.0)
        client = MockExchangeClient(config, mock_data_source)

        base_price = 200.0

        buy_price = client._apply_slippage(base_price, "buy")
        sell_price = client._apply_slippage(base_price, "sell")

        # 買い: 200 * (1 + 50/10000) = 200 * 1.005 = 201
        assert buy_price == pytest.approx(201.0, rel=1e-6)
        # 売り: 200 * (1 - 50/10000) = 200 * 0.995 = 199
        assert sell_price == pytest.approx(199.0, rel=1e-6)


class TestMockExchangeClientMarketOrder:
    """MockExchangeClient成行注文処理のテスト"""

    def test_process_market_order_next_open_price(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """market_fill_price_type="next_open"で翌バーのopenで約定"""
        from qeel.exchange_clients.mock import MockExchangeClient

        # デフォルトはnext_open
        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        fill = client._process_market_order("AAPL", "buy", 10.0)

        assert fill is not None
        # 翌バー（1/2）のopen: 105.0 + slippage (10bps)
        expected_price = 105.0 * 1.001  # 105.105
        assert fill["filled_price"] == pytest.approx(expected_price, rel=1e-6)
        assert fill["timestamp"] == datetime(2024, 1, 2, 9, 0)

    def test_process_market_order_current_close_price(self, mock_data_source: MagicMock) -> None:
        """market_fill_price_type="current_close"で当バーのcloseで約定"""
        from qeel.exchange_clients.mock import MockExchangeClient

        config = CostConfig(
            commission_rate=0.001,
            slippage_bps=10.0,
            market_fill_price_type="current_close",
        )
        client = MockExchangeClient(config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        fill = client._process_market_order("AAPL", "buy", 10.0)

        assert fill is not None
        # 当バー（1/1）のclose: 105.0 + slippage (10bps)
        expected_price = 105.0 * 1.001  # 105.105
        assert fill["filled_price"] == pytest.approx(expected_price, rel=1e-6)
        assert fill["timestamp"] == datetime(2024, 1, 1, 9, 0)

    def test_process_market_order_applies_slippage(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """スリッページが適用される"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        buy_fill = client._process_market_order("AAPL", "buy", 10.0)
        sell_fill = client._process_market_order("AAPL", "sell", 10.0)

        assert buy_fill is not None
        assert sell_fill is not None
        # 翌バーのopen: 105.0
        # 買い: 105.0 * 1.001 = 105.105
        # 売り: 105.0 * 0.999 = 104.895
        assert buy_fill["filled_price"] > 105.0
        assert sell_fill["filled_price"] < 105.0

    def test_process_market_order_calculates_commission(
        self, cost_config: CostConfig, mock_data_source: MagicMock
    ) -> None:
        """手数料が正しく計算される（filled_price * quantity * commission_rate）"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        fill = client._process_market_order("AAPL", "buy", 10.0)

        assert fill is not None
        expected_commission = fill["filled_price"] * 10.0 * 0.001
        assert fill["commission"] == pytest.approx(expected_commission, rel=1e-6)

    def test_process_market_order_returns_none_when_no_next_bar(
        self, cost_config: CostConfig, mock_data_source: MagicMock
    ) -> None:
        """翌バーがない場合Noneを返す"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        # 最終バー（1/3）の時点に設定
        client.set_current_datetime(datetime(2024, 1, 3, 9, 0))

        fill = client._process_market_order("AAPL", "buy", 10.0)

        assert fill is None

    def test_process_market_order_fill_structure(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """約定情報の構造が正しい"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        fill = client._process_market_order("AAPL", "buy", 10.0)

        assert fill is not None
        assert "order_id" in fill
        assert "symbol" in fill
        assert "side" in fill
        assert "filled_quantity" in fill
        assert "filled_price" in fill
        assert "commission" in fill
        assert "timestamp" in fill

        assert fill["symbol"] == "AAPL"
        assert fill["side"] == "buy"
        assert fill["filled_quantity"] == 10.0

    def test_process_market_order_last_bar_multiple_orders(
        self, cost_config: CostConfig, mock_data_source: MagicMock
    ) -> None:
        """最終バー付近で複数注文を実行した場合、翌バーがない注文のみNoneを返す"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL", "GOOGL"])
        # 2番目のバー（1/2）の時点に設定
        client.set_current_datetime(datetime(2024, 1, 2, 9, 0))

        # AAPLの注文（翌バー1/3が存在）
        aapl_fill = client._process_market_order("AAPL", "buy", 10.0)
        assert aapl_fill is not None

        # 最終バー（1/3）の時点に設定
        client.set_current_datetime(datetime(2024, 1, 3, 9, 0))

        # AAPLの注文（翌バーが存在しない）
        aapl_fill_no_next = client._process_market_order("AAPL", "buy", 10.0)
        assert aapl_fill_no_next is None


class TestMockExchangeClientLimitOrder:
    """MockExchangeClient指値注文処理のテスト"""

    def test_process_limit_order_buy_fills_when_price_above_low(
        self, cost_config: CostConfig, mock_data_source: MagicMock
    ) -> None:
        """買い指値が翌バーのlowより高い場合約定"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        # 翌バー（1/2）のlow: 102.0
        # 指値103.0 > low102.0 なので約定
        fill = client._process_limit_order("AAPL", "buy", 10.0, 103.0)

        assert fill is not None
        assert fill["filled_price"] == 103.0

    def test_process_limit_order_buy_not_fills_when_price_equals_low(
        self, cost_config: CostConfig, mock_data_source: MagicMock
    ) -> None:
        """買い指値が翌バーのlowと同値の場合未約定"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        # 翌バー（1/2）のlow: 102.0
        # 指値102.0 == low102.0 なので未約定
        fill = client._process_limit_order("AAPL", "buy", 10.0, 102.0)

        assert fill is None

    def test_process_limit_order_sell_fills_when_price_below_high(
        self, cost_config: CostConfig, mock_data_source: MagicMock
    ) -> None:
        """売り指値が翌バーのhighより低い場合約定"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        # 翌バー（1/2）のhigh: 115.0
        # 指値114.0 < high115.0 なので約定
        fill = client._process_limit_order("AAPL", "sell", 10.0, 114.0)

        assert fill is not None
        assert fill["filled_price"] == 114.0

    def test_process_limit_order_sell_not_fills_when_price_equals_high(
        self, cost_config: CostConfig, mock_data_source: MagicMock
    ) -> None:
        """売り指値が翌バーのhighと同値の場合未約定"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        # 翌バー（1/2）のhigh: 115.0
        # 指値115.0 == high115.0 なので未約定
        fill = client._process_limit_order("AAPL", "sell", 10.0, 115.0)

        assert fill is None

    def test_process_limit_order_fills_at_limit_price(
        self, cost_config: CostConfig, mock_data_source: MagicMock
    ) -> None:
        """約定価格は指値価格そのもの（スリッページなし）"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        limit_price = 103.0
        fill = client._process_limit_order("AAPL", "buy", 10.0, limit_price)

        assert fill is not None
        # 指値価格そのものが約定価格（スリッページなし）
        assert fill["filled_price"] == limit_price

    def test_process_limit_order_calculates_commission(
        self, cost_config: CostConfig, mock_data_source: MagicMock
    ) -> None:
        """手数料が正しく計算される"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        limit_price = 103.0
        quantity = 10.0
        fill = client._process_limit_order("AAPL", "buy", quantity, limit_price)

        assert fill is not None
        expected_commission = limit_price * quantity * 0.001
        assert fill["commission"] == pytest.approx(expected_commission, rel=1e-6)

    def test_process_limit_order_returns_none_when_no_next_bar(
        self, cost_config: CostConfig, mock_data_source: MagicMock
    ) -> None:
        """翌バーがない場合Noneを返す"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        # 最終バー（1/3）の時点に設定
        client.set_current_datetime(datetime(2024, 1, 3, 9, 0))

        fill = client._process_limit_order("AAPL", "buy", 10.0, 100.0)

        assert fill is None

    def test_process_limit_order_float_comparison_edge_case(
        self, cost_config: CostConfig, mock_data_source: MagicMock
    ) -> None:
        """浮動小数点比較で同値判定が正しく動作する"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        # 翌バー（1/2）のlow: 102.0
        # 同値（102.0）は未約定
        fill_exact = client._process_limit_order("AAPL", "buy", 10.0, 102.0)
        assert fill_exact is None

        # 102.01 > 102.0 なので約定
        fill_above = client._process_limit_order("AAPL", "buy", 10.0, 102.01)
        assert fill_above is not None


class TestMockExchangeClientSubmitOrders:
    """MockExchangeClient submit_ordersのテスト"""

    def test_submit_orders_validates_schema(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """OrderSchemaバリデーションが実行される"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        # 不正なスキーマ（必須列不足）
        invalid_orders = pl.DataFrame({"symbol": ["AAPL"]})

        with pytest.raises(ValueError, match="必須列が不足"):
            client.submit_orders(invalid_orders)

    def test_submit_orders_processes_market_orders(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """成行注文が正しく処理される"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
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

        # fill_historyに約定情報が追加される
        assert len(client.fill_history) == 1

    def test_submit_orders_processes_limit_orders(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """指値注文が正しく処理される"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        orders = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["buy"],
                "quantity": [10.0],
                "price": [103.0],  # 翌バーのlow(102.0)より高いので約定
                "order_type": ["limit"],
            }
        )

        client.submit_orders(orders)

        assert len(client.fill_history) == 1

    def test_submit_orders_processes_mixed_orders(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """成行と指値の混合注文が処理される"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        orders = pl.DataFrame(
            {
                "symbol": ["AAPL", "AAPL"],
                "side": ["buy", "sell"],
                "quantity": [10.0, 5.0],
                "price": [None, 114.0],  # 成行と指値
                "order_type": ["market", "limit"],
            }
        )

        client.submit_orders(orders)

        # 成行は約定、指値(114.0 < high115.0)も約定
        assert len(client.fill_history) == 1
        assert client.fill_history[0].height == 2

    def test_submit_orders_stores_fills_in_history(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """約定情報がfill_historyに追加される"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
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

        assert len(client.fill_history) == 1

    def test_submit_orders_raises_on_limit_without_price(
        self, cost_config: CostConfig, mock_data_source: MagicMock
    ) -> None:
        """指値注文でpriceがNoneの場合ValueError"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        orders = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["buy"],
                "quantity": [10.0],
                "price": [None],  # 指値なのにpriceがNone
                "order_type": ["limit"],
            }
        )

        with pytest.raises(ValueError, match="指値注文にはpriceが必須"):
            client.submit_orders(orders)


class TestMockExchangeClientFetchFills:
    """MockExchangeClient fetch_fillsのテスト"""

    def test_fetch_fills_returns_empty_when_no_fills(
        self, cost_config: CostConfig, mock_data_source: MagicMock
    ) -> None:
        """約定がない場合空DataFrameを返す"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)

        fills = client.fetch_fills(datetime(2024, 1, 1), datetime(2024, 1, 5))

        assert fills.height == 0
        # スキーマの列は存在する
        assert "order_id" in fills.columns
        assert "symbol" in fills.columns
        assert "side" in fills.columns
        assert "filled_quantity" in fills.columns
        assert "filled_price" in fills.columns
        assert "commission" in fills.columns
        assert "timestamp" in fills.columns

    def test_fetch_fills_returns_fills_in_range(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """指定期間内の約定のみを返す"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        orders = pl.DataFrame(
            {
                "symbol": ["AAPL", "AAPL"],
                "side": ["buy", "sell"],
                "quantity": [10.0, 5.0],
                "price": [None, None],
                "order_type": ["market", "market"],
            }
        )

        client.submit_orders(orders)
        # 約定は翌バー（2024-01-02）で発生
        fills = client.fetch_fills(datetime(2024, 1, 1), datetime(2024, 1, 3))

        assert fills.height == 2

    def test_fetch_fills_can_fetch_multiple_times(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """同じ期間を何度でも取得可能"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
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
        fills1 = client.fetch_fills(datetime(2024, 1, 1), datetime(2024, 1, 5))
        fills2 = client.fetch_fills(datetime(2024, 1, 1), datetime(2024, 1, 5))

        # 何度でも同じ結果が取得できる
        assert fills1.height == 1
        assert fills2.height == 1
        assert fills1.equals(fills2)

    def test_fetch_fills_filters_by_date_range(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """期間外の約定は除外される"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
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
        # 約定は翌バー（2024-01-02）で発生するので、2024-01-01のみの期間では取得できない
        fills = client.fetch_fills(datetime(2024, 1, 1), datetime(2024, 1, 1, 23, 59, 59))

        assert fills.height == 0

    def test_fetch_fills_validates_schema(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """FillReportSchemaバリデーションが実行される"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
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
        # バリデーションはエラーなく通過する
        fills = client.fetch_fills(datetime(2024, 1, 1), datetime(2024, 1, 5))
        assert fills.height == 1

    def test_fetch_fills_schema_compliance(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """返却DataFrameがFillReportSchemaに準拠"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
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
        fills = client.fetch_fills(datetime(2024, 1, 1), datetime(2024, 1, 5))

        # FillReportSchemaの全列が存在
        assert fills["order_id"].dtype == pl.Utf8
        assert fills["symbol"].dtype == pl.Utf8
        assert fills["side"].dtype == pl.Utf8
        assert fills["filled_quantity"].dtype == pl.Float64
        assert fills["filled_price"].dtype == pl.Float64
        assert fills["commission"].dtype == pl.Float64
        assert fills["timestamp"].dtype == pl.Datetime


class TestMockExchangeClientFetchPositions:
    """MockExchangeClient fetch_positionsのテスト"""

    def test_fetch_positions_returns_empty_when_no_history(
        self, cost_config: CostConfig, mock_data_source: MagicMock
    ) -> None:
        """約定履歴がない場合空DataFrameを返す"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)

        positions = client.fetch_positions()

        assert positions.height == 0
        # スキーマの列は存在する
        assert "symbol" in positions.columns
        assert "quantity" in positions.columns
        assert "avg_price" in positions.columns

    def test_fetch_positions_calculates_from_buys(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """買い約定からポジション数量を計算"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
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
        positions = client.fetch_positions()

        assert positions.height == 1
        assert positions["symbol"][0] == "AAPL"
        assert positions["quantity"][0] == pytest.approx(10.0, rel=1e-6)

    def test_fetch_positions_calculates_from_sells(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """売り約定でポジション数量が減少"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        # 買い10、売り3 = 残り7
        buy_orders = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["buy"],
                "quantity": [10.0],
                "price": [None],
                "order_type": ["market"],
            }
        )
        client.submit_orders(buy_orders)

        sell_orders = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["sell"],
                "quantity": [3.0],
                "price": [None],
                "order_type": ["market"],
            }
        )
        client.submit_orders(sell_orders)

        positions = client.fetch_positions()

        assert positions.height == 1
        assert positions["quantity"][0] == pytest.approx(7.0, rel=1e-6)

    def test_fetch_positions_calculates_avg_price(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """平均取得単価を正しく計算（買いの加重平均）"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        # 1回目: 10株
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

        # 日付を進めて2回目の買い
        client.set_current_datetime(datetime(2024, 1, 2, 9, 0))
        orders2 = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["buy"],
                "quantity": [20.0],
                "price": [None],
                "order_type": ["market"],
            }
        )
        client.submit_orders(orders2)

        positions = client.fetch_positions()

        # 平均取得単価は加重平均で計算される
        assert positions.height == 1
        assert positions["quantity"][0] == pytest.approx(30.0, rel=1e-6)
        # avg_price > 0 を確認（具体値はスリッページにより変動）
        assert positions["avg_price"][0] > 0

    def test_fetch_positions_excludes_zero_positions(
        self, cost_config: CostConfig, mock_data_source: MagicMock
    ) -> None:
        """数量ゼロのポジションは除外"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        # 買い10、売り10 = 残り0
        buy_orders = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["buy"],
                "quantity": [10.0],
                "price": [None],
                "order_type": ["market"],
            }
        )
        client.submit_orders(buy_orders)

        sell_orders = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["sell"],
                "quantity": [10.0],
                "price": [None],
                "order_type": ["market"],
            }
        )
        client.submit_orders(sell_orders)

        positions = client.fetch_positions()

        # 数量ゼロなので除外される
        assert positions.height == 0

    def test_fetch_positions_handles_multiple_symbols(
        self, cost_config: CostConfig, mock_data_source: MagicMock
    ) -> None:
        """複数銘柄を正しく集計"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL", "GOOGL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

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
        positions = client.fetch_positions()

        assert positions.height == 2
        symbols = positions["symbol"].to_list()
        assert "AAPL" in symbols
        assert "GOOGL" in symbols

    def test_fetch_positions_validates_schema(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """PositionSchemaバリデーションが実行される"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
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
        # バリデーションはエラーなく通過する
        positions = client.fetch_positions()
        assert positions.height == 1

    def test_fetch_positions_allows_short_positions(self, cost_config: CostConfig, mock_data_source: MagicMock) -> None:
        """ショートポジション（マイナス数量）を許容し、正しく返す"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        # 先に売り（ショートポジション）
        sell_orders = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["sell"],
                "quantity": [10.0],
                "price": [None],
                "order_type": ["market"],
            }
        )
        client.submit_orders(sell_orders)

        positions = client.fetch_positions()

        # ショートポジション（マイナス数量）
        assert positions.height == 1
        assert positions["quantity"][0] == pytest.approx(-10.0, rel=1e-6)

    def test_fetch_positions_short_avg_price_calculation(
        self, cost_config: CostConfig, mock_data_source: MagicMock
    ) -> None:
        """ショートポジションの平均取得単価は売りの加重平均"""
        from qeel.exchange_clients.mock import MockExchangeClient

        client = MockExchangeClient(cost_config, mock_data_source)
        client.load_ohlcv(datetime(2024, 1, 1), datetime(2024, 1, 5), ["AAPL"])
        client.set_current_datetime(datetime(2024, 1, 1, 9, 0))

        # 売りのみ
        sell_orders = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["sell"],
                "quantity": [10.0],
                "price": [None],
                "order_type": ["market"],
            }
        )
        client.submit_orders(sell_orders)

        positions = client.fetch_positions()

        # ショートなので平均単価は売りの価格ベース
        assert positions["avg_price"][0] > 0
