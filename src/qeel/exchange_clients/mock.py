"""バックテスト用モック取引所クライアント

成行注文・指値注文のシミュレーション、スリッページ・手数料計算を提供する。
OHLCVデータはBaseDataSource経由で取得する。
"""

import uuid
from datetime import datetime

import polars as pl

from qeel.config import CostConfig
from qeel.data_sources.base import BaseDataSource
from qeel.exchange_clients.base import BaseExchangeClient
from qeel.schemas import FillReportSchema, PositionSchema


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

        TODO: 取引日の判定が正確でない可能性がある。
              current_datetimeより後の最初のバーを単純に取得しているが、
              休場日・祝日・取引時間外を考慮していない。
              See: https://github.com/jintonic3561/qeel/issues/11
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

        TODO: 取引日の判定が正確でない可能性がある。
              current_datetime以前の最新バーを単純に取得しているが、
              休場日・祝日・取引時間外を考慮していない。
              See: https://github.com/jintonic3561/qeel/issues/11
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

        order_rows = orders.to_dicts()

        for row in order_rows:
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
            self.fill_history.append(fills)

    def fetch_fills(self, start: datetime, end: datetime) -> pl.DataFrame:
        """指定期間の約定情報を取得する

        Args:
            start: 取得開始日時
            end: 取得終了日時

        Returns:
            期間内の約定情報（FillReportSchema準拠）
        """
        if not self.fill_history:
            return pl.DataFrame(schema=FillReportSchema.REQUIRED_COLUMNS)

        all_fills = pl.concat(self.fill_history)
        filtered = all_fills.filter((pl.col("timestamp") >= start) & (pl.col("timestamp") <= end))

        if filtered.height == 0:
            return pl.DataFrame(schema=FillReportSchema.REQUIRED_COLUMNS)

        return self._validate_fills(filtered)

    def fetch_positions(self) -> pl.DataFrame:
        """約定履歴から現在のポジションを計算する

        時系列順に約定を処理し、平均取得単価を正しく更新する。

        Returns:
            PositionSchemaに準拠したPolars DataFrame
        """
        if not self.fill_history:
            return pl.DataFrame(schema=PositionSchema.REQUIRED_COLUMNS)

        # 全約定を結合し、タイムスタンプ順にソート
        all_fills = pl.concat(self.fill_history).sort("timestamp")

        # iter_rows(named=True) は遅いため、to_dicts() で一括変換してから処理する
        fill_rows = all_fills.to_dicts()

        # 銘柄ごとのポジション状態管理
        # key: symbol, value: {"quantity": float, "avg_price": float}
        positions_map: dict[str, dict[str, float]] = {}

        for row in fill_rows:
            symbol = row["symbol"]
            side = row["side"]
            price = row["filled_price"]
            qty = row["filled_quantity"]

            # 符号付き数量（買い: +, 売り: -）
            signed_qty = qty if side == "buy" else -qty

            if symbol not in positions_map:
                positions_map[symbol] = {"quantity": 0.0, "avg_price": 0.0}

            pos = positions_map[symbol]
            current_qty = pos["quantity"]
            current_avg = pos["avg_price"]

            if current_qty == 0:
                # ポジションなし -> 新規エントリー
                pos["quantity"] = signed_qty
                pos["avg_price"] = price

            elif (current_qty > 0 and signed_qty > 0) or (current_qty < 0 and signed_qty < 0):
                # 積み増し（同方向） -> 加重平均価格を更新
                new_qty = current_qty + signed_qty
                total_value = (current_qty * current_avg) + (signed_qty * price)
                pos["quantity"] = new_qty
                pos["avg_price"] = total_value / new_qty

            elif (current_qty > 0 > signed_qty) or (current_qty < 0 < signed_qty):
                # 決済方向（逆方向）
                if abs(current_qty) > abs(signed_qty):
                    # 一部決済 -> 平均単価は変わらず、数量のみ減少
                    pos["quantity"] += signed_qty
                elif abs(current_qty) == abs(signed_qty):
                    # 全決済 -> ポジション解消
                    pos["quantity"] = 0.0
                    pos["avg_price"] = 0.0
                else:
                    # ドテン（決済して逆方向へ）
                    # 残りの数量分が新規ポジションとなる
                    remaining_qty = signed_qty + current_qty  # 符号付きの残数量
                    pos["quantity"] = remaining_qty
                    pos["avg_price"] = price  # 新規分の価格になる

        # 結果をリスト化
        result_data = []
        for symbol, data in positions_map.items():
            # 数量が0でない（ポジションがある）ものだけ抽出
            if data["quantity"] != 0:
                result_data.append({"symbol": symbol, "quantity": data["quantity"], "avg_price": data["avg_price"]})

        if not result_data:
            return pl.DataFrame(schema=PositionSchema.REQUIRED_COLUMNS)

        positions_df = pl.DataFrame(result_data)

        return self._validate_positions(positions_df)
