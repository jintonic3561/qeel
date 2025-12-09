"""バックテスト用モック取引所クライアント

成行注文・指値注文のシミュレーション、スリッページ・手数料計算を提供する。
OHLCVデータはBaseDataSource経由で取得する。
"""

from datetime import datetime

import polars as pl

from qeel.config import CostConfig
from qeel.data_sources.base import BaseDataSource
from qeel.exchange_clients.base import BaseExchangeClient


class MockExchangeClient(BaseExchangeClient):
    """バックテスト用モック取引所クライアント

    実運用との整合性を最大化したモック実装。
    - 成行注文: 翌バーのopen（またはconfigで当バーのclose）+スリッページで約定
    - 指値注文: 翌バーのhigh/lowで約定判定、同値は未約定
    - スリッページ: 買いは+（不利方向）、売りは-（不利方向）
    - 手数料: 約定価格×約定数量×手数料率で計算

    OHLCVデータはBaseDataSource経由で取得し、一貫したデータアクセスを実現する。
    """

    def __init__(self, config: CostConfig, ohlcv_data_source: BaseDataSource) -> None:
        """初期化

        Args:
            config: コスト設定
            ohlcv_data_source: OHLCVデータソース（BaseDataSource実装）
        """
        self.config = config
        self.ohlcv_data_source = ohlcv_data_source
        self.ohlcv_cache: pl.DataFrame | None = None
        self.current_datetime: datetime | None = None
        self.pending_fills: list[pl.DataFrame] = []
        self.fill_history: list[pl.DataFrame] = []

    def load_ohlcv(self, start: datetime, end: datetime, symbols: list[str]) -> None:
        """OHLCVデータをDataSourceから読み込みキャッシュする

        バックテスト開始時に呼び出し、全期間のOHLCVデータをキャッシュする。
        これにより、各iterationで効率的に翌バー/当バーを参照可能。

        Args:
            start: バックテスト開始日時
            end: バックテスト終了日時（翌バー参照のため余裕を持たせる）
            symbols: 対象銘柄リスト
        """
        self.ohlcv_cache = self.ohlcv_data_source.fetch(start, end, symbols)

    def set_current_datetime(self, dt: datetime) -> None:
        """現在のiteration日時を設定する

        Args:
            dt: 現在のiteration日時
        """
        self.current_datetime = dt

    def _get_next_bar(self, symbol: str) -> pl.DataFrame | None:
        """指定銘柄の翌バーのOHLCVを取得する

        Args:
            symbol: 銘柄コード

        Returns:
            翌バーのOHLCVデータ（1行）、または存在しない場合None
        """
        if self.ohlcv_cache is None or self.current_datetime is None:
            return None

        # current_datetimeより後の最初のバーを取得
        next_bars = (
            self.ohlcv_cache.filter((pl.col("symbol") == symbol) & (pl.col("datetime") > self.current_datetime))
            .sort("datetime")
            .head(1)
        )

        if next_bars.height == 0:
            return None
        return next_bars

    def _get_current_bar(self, symbol: str) -> pl.DataFrame | None:
        """指定銘柄の当バーのOHLCVを取得する

        Args:
            symbol: 銘柄コード

        Returns:
            当バーのOHLCVデータ（1行）、または存在しない場合None
        """
        if self.ohlcv_cache is None or self.current_datetime is None:
            return None

        # current_datetime以前の最新バーを取得
        current_bars = (
            self.ohlcv_cache.filter((pl.col("symbol") == symbol) & (pl.col("datetime") <= self.current_datetime))
            .sort("datetime", descending=True)
            .head(1)
        )

        if current_bars.height == 0:
            return None
        return current_bars

    def _apply_slippage(self, price: float, side: str) -> float:
        """スリッページを適用する

        買い: +slippage（不利方向=高く買う）
        売り: -slippage（不利方向=安く売る）

        Args:
            price: 基準価格
            side: 売買区分（"buy" or "sell"）

        Returns:
            スリッページ適用後の価格
        """
        slippage_rate = self.config.slippage_bps / 10000.0
        if side == "buy":
            return price * (1 + slippage_rate)
        else:  # sell
            return price * (1 - slippage_rate)

    def _process_market_order(
        self, symbol: str, side: str, quantity: float
    ) -> dict[str, str | float | datetime] | None:
        """成行注文を処理する

        Args:
            symbol: 銘柄コード
            side: 売買区分（"buy" or "sell"）
            quantity: 注文数量

        Returns:
            約定情報の辞書、または約定不可の場合None
        """
        import uuid

        # 約定価格の基準を取得
        if self.config.market_fill_price_type == "next_open":
            bar = self._get_next_bar(symbol)
            if bar is None:
                return None  # 翌バーがない場合は約定不可
            base_price = bar["open"][0]
            fill_time = bar["datetime"][0]
        else:  # current_close
            bar = self._get_current_bar(symbol)
            if bar is None:
                return None
            base_price = bar["close"][0]
            fill_time = bar["datetime"][0]

        # スリッページ適用
        filled_price = self._apply_slippage(base_price, side)

        # 手数料計算（約定価格ベース）
        commission = filled_price * quantity * self.config.commission_rate

        return {
            "order_id": str(uuid.uuid4()),
            "symbol": symbol,
            "side": side,
            "filled_quantity": quantity,
            "filled_price": filled_price,
            "commission": commission,
            "timestamp": fill_time,
        }

    def _process_limit_order(
        self, symbol: str, side: str, quantity: float, limit_price: float
    ) -> dict[str, str | float | datetime] | None:
        """指値注文を処理する

        翌バーのhigh/lowで約定判定:
        - 買い指値: limit_price > low なら約定
        - 売り指値: limit_price < high なら約定
        - 同値は未約定

        Args:
            symbol: 銘柄コード
            side: 売買区分（"buy" or "sell"）
            quantity: 注文数量
            limit_price: 指値価格

        Returns:
            約定情報の辞書、または約定不可の場合None
        """
        import uuid

        next_bar = self._get_next_bar(symbol)
        if next_bar is None:
            return None  # 翌バーがない場合は約定不可

        high = next_bar["high"][0]
        low = next_bar["low"][0]
        fill_time = next_bar["datetime"][0]

        # 約定判定（同値は未約定）
        if side == "buy":
            # 買い指値: 指値 > low なら約定（指値 == low は未約定）
            if limit_price <= low:
                return None
        else:  # sell
            # 売り指値: 指値 < high なら約定（指値 == high は未約定）
            if limit_price >= high:
                return None

        # 指値で約定（スリッページなし）
        filled_price = limit_price

        # 手数料計算（約定価格ベース）
        commission = filled_price * quantity * self.config.commission_rate

        return {
            "order_id": str(uuid.uuid4()),
            "symbol": symbol,
            "side": side,
            "filled_quantity": quantity,
            "filled_price": filled_price,
            "commission": commission,
            "timestamp": fill_time,
        }

    def submit_orders(self, orders: pl.DataFrame) -> None:
        """注文を執行する

        成行注文は即座に約定処理、指値注文は翌バーで約定判定を行う。

        Args:
            orders: OrderSchemaに準拠したPolars DataFrame

        Raises:
            ValueError: 注文が不正な場合
        """
        # 共通バリデーションヘルパーを使用
        self._validate_orders(orders)

        fills_data: list[dict[str, str | float | datetime]] = []

        for row in orders.iter_rows(named=True):
            symbol = row["symbol"]
            side = row["side"]
            quantity = row["quantity"]
            price = row["price"]
            order_type = row["order_type"]

            if order_type == "market":
                fill = self._process_market_order(symbol, side, quantity)
                if fill:
                    fills_data.append(fill)
            elif order_type == "limit":
                if price is None:
                    raise ValueError(f"指値注文にはpriceが必須です: {symbol}")
                fill = self._process_limit_order(symbol, side, quantity, price)
                if fill:
                    fills_data.append(fill)

        if fills_data:
            fills = pl.DataFrame(fills_data)
            self.pending_fills.append(fills)
            self.fill_history.append(fills)

    def fetch_fills(self) -> pl.DataFrame:
        """約定情報を取得する

        Returns:
            FillReportSchemaに準拠したPolars DataFrame
        """
        from qeel.schemas import FillReportSchema

        if not self.pending_fills:
            return pl.DataFrame(schema=FillReportSchema.REQUIRED_COLUMNS)

        all_fills = pl.concat(self.pending_fills)
        self.pending_fills.clear()

        return self._validate_fills(all_fills)

    def fetch_positions(self) -> pl.DataFrame:
        """約定履歴から現在のポジションを計算する

        ショートポジション（マイナス数量）を許容。
        平均取得単価はロングなら買いの加重平均、ショートなら売りの加重平均。

        Returns:
            PositionSchemaに準拠したPolars DataFrame
        """
        from qeel.schemas import PositionSchema

        if not self.fill_history:
            return pl.DataFrame(schema=PositionSchema.REQUIRED_COLUMNS)

        all_fills = pl.concat(self.fill_history)

        # ポジションを累積計算（加重平均価格を計算）
        positions = (
            all_fills.with_columns(
                [
                    # 買いは+、売りは-として数量を符号付きに
                    pl.when(pl.col("side") == "buy")
                    .then(pl.col("filled_quantity"))
                    .otherwise(-pl.col("filled_quantity"))
                    .alias("signed_quantity"),
                    # 買い約定金額（ロングの加重平均計算用）
                    pl.when(pl.col("side") == "buy")
                    .then(pl.col("filled_quantity") * pl.col("filled_price"))
                    .otherwise(pl.lit(0.0))
                    .alias("buy_value"),
                    pl.when(pl.col("side") == "buy")
                    .then(pl.col("filled_quantity"))
                    .otherwise(pl.lit(0.0))
                    .alias("buy_quantity"),
                    # 売り約定金額（ショートの加重平均計算用）
                    pl.when(pl.col("side") == "sell")
                    .then(pl.col("filled_quantity") * pl.col("filled_price"))
                    .otherwise(pl.lit(0.0))
                    .alias("sell_value"),
                    pl.when(pl.col("side") == "sell")
                    .then(pl.col("filled_quantity"))
                    .otherwise(pl.lit(0.0))
                    .alias("sell_quantity"),
                ]
            )
            .group_by("symbol")
            .agg(
                [
                    pl.col("signed_quantity").sum().alias("quantity"),
                    pl.col("buy_value").sum().alias("total_buy_value"),
                    pl.col("buy_quantity").sum().alias("total_buy_quantity"),
                    pl.col("sell_value").sum().alias("total_sell_value"),
                    pl.col("sell_quantity").sum().alias("total_sell_quantity"),
                ]
            )
            .filter(pl.col("quantity") != 0)
            .with_columns(
                [
                    # 平均取得単価: ロング（正）は買いの加重平均、ショート（負）は売りの加重平均
                    pl.when(pl.col("quantity") > 0)
                    .then(
                        pl.when(pl.col("total_buy_quantity") > 0)
                        .then(pl.col("total_buy_value") / pl.col("total_buy_quantity"))
                        .otherwise(pl.lit(0.0))
                    )
                    .otherwise(
                        pl.when(pl.col("total_sell_quantity") > 0)
                        .then(pl.col("total_sell_value") / pl.col("total_sell_quantity"))
                        .otherwise(pl.lit(0.0))
                    )
                    .alias("avg_price"),
                ]
            )
            .select(["symbol", "quantity", "avg_price"])
        )

        return self._validate_positions(positions)
