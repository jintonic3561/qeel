# Contract: BaseExchangeClient

## 概要

注文の執行、約定情報の取得、ポジション情報の取得を抽象化するインターフェース。バックテスト時はモック、実運用時は取引所APIを使用する。

## インターフェース定義

```python
from abc import ABC, abstractmethod
from datetime import datetime

import polars as pl


class BaseExchangeClient(ABC):
    """取引所クライアント抽象基底クラス

    バックテストではモック約定とポジション管理、実運用では取引所API呼び出しを実装する。
    """

    def _validate_orders(self, orders: pl.DataFrame) -> None:
        """注文DataFrameの共通バリデーション

        サブクラスで任意に呼び出し可能なヘルパーメソッド。
        スキーマバリデーションを一箇所で実行し、重複を避ける。

        Args:
            orders: 注文DataFrame（OrderSchema準拠）

        Raises:
            ValueError: スキーマ違反の場合
        """
        from qeel.schemas import OrderSchema

        OrderSchema.validate(orders)

    def _validate_fills(self, fills: pl.DataFrame) -> pl.DataFrame:
        """約定情報DataFrameの共通バリデーション

        サブクラスで任意に呼び出し可能なヘルパーメソッド。
        スキーマバリデーションを一箇所で実行し、重複を避ける。

        Args:
            fills: 約定情報DataFrame（FillReportSchema準拠）

        Returns:
            バリデーション済みのDataFrame

        Raises:
            ValueError: スキーマ違反の場合
        """
        from qeel.schemas import FillReportSchema

        return FillReportSchema.validate(fills)

    def _validate_positions(self, positions: pl.DataFrame) -> pl.DataFrame:
        """ポジション情報DataFrameの共通バリデーション

        サブクラスで任意に呼び出し可能なヘルパーメソッド。
        スキーマバリデーションを一箇所で実行し、重複を避ける。

        Args:
            positions: ポジション情報DataFrame（PositionSchema準拠）

        Returns:
            バリデーション済みのDataFrame

        Raises:
            ValueError: スキーマ違反の場合
        """
        from qeel.schemas import PositionSchema

        return PositionSchema.validate(positions)

    @abstractmethod
    def submit_orders(self, orders: pl.DataFrame) -> None:
        """注文を執行する

        Args:
            orders: OrderSchemaに準拠したPolars DataFrame

        Raises:
            ValueError: 注文が不正な場合（スキーマ違反、数量ゼロ等）
            RuntimeError: 実運用時のAPI呼び出しエラー（ユーザ実装で処理）
        """
        ...

    @abstractmethod
    def fetch_fills(self, start: datetime, end: datetime) -> pl.DataFrame:
        """指定期間の約定情報を取得する

        Args:
            start: 取得開始日時
            end: 取得終了日時

        Returns:
            FillReportSchemaに準拠したPolars DataFrame

        Raises:
            RuntimeError: 実運用時のAPI呼び出しエラー（ユーザ実装で処理）
        """
        ...

    @abstractmethod
    def fetch_positions(self) -> pl.DataFrame:
        """現在のポジションを取得する

        バックテスト: 約定履歴から計算した現在のポジションを返す
        実運用: 取引所APIから現在のポジションを取得して返す

        Returns:
            PositionSchemaに準拠したPolars DataFrame

        Raises:
            RuntimeError: 実運用時のAPI呼び出しエラー（ユーザ実装で処理）
        """
        ...
```

## 実装例

### Backtest用モック実装

```python
import uuid
from datetime import datetime, timedelta

import polars as pl

from qeel.config import CostConfig
from qeel.data_sources import BaseDataSource
from qeel.exchange_clients import BaseExchangeClient
from qeel.schemas import FillReportSchema, OrderSchema, PositionSchema


class MockExchangeClient(BaseExchangeClient):
    """バックテスト用モック取引所クライアント

    実運用との整合性を最大化したモック実装。
    - 成行注文: 翌バーのopen（またはconfigで当バーのclose）+スリッページで約定
    - 指値注文: 翌バーのhigh/lowで約定判定、同値は未約定
    - スリッページ: 買いは+（不利方向）、売りは-（不利方向）
    - 手数料: 約定価格×約定数量×手数料率で計算

    OHLCVデータはBaseDataSource経由で取得し、一貫したデータアクセスを実現する。
    """

    def __init__(self, config: CostConfig, ohlcv_data_source: BaseDataSource):
        """
        Args:
            config: コスト設定
            ohlcv_data_source: OHLCVデータソース（BaseDataSource実装）
        """
        self.config = config
        self.ohlcv_data_source = ohlcv_data_source
        self.ohlcv_cache: pl.DataFrame | None = None  # OHLCVデータキャッシュ
        self.current_datetime: datetime | None = None  # 現在のiteration日時
        self.fill_history: list[pl.DataFrame] = []  # 約定履歴（fetch_fills, fetch_positions用）

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
        """指定銘柄の翌バーのOHLCVを取得する"""
        if self.ohlcv_cache is None or self.current_datetime is None:
            return None

        # current_datetimeより後の最初のバーを取得
        next_bars = (
            self.ohlcv_cache
            .filter(
                (pl.col("symbol") == symbol) &
                (pl.col("datetime") > self.current_datetime)
            )
            .sort("datetime")
            .head(1)
        )

        if next_bars.height == 0:
            return None
        return next_bars

    def _get_current_bar(self, symbol: str) -> pl.DataFrame | None:
        """指定銘柄の当バーのOHLCVを取得する"""
        if self.ohlcv_cache is None or self.current_datetime is None:
            return None

        # current_datetime以前の最新バーを取得
        current_bars = (
            self.ohlcv_cache
            .filter(
                (pl.col("symbol") == symbol) &
                (pl.col("datetime") <= self.current_datetime)
            )
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
        """
        slippage_rate = self.config.slippage_bps / 10000.0
        if side == "buy":
            return price * (1 + slippage_rate)
        else:  # sell
            return price * (1 - slippage_rate)

    def _process_market_order(
        self, symbol: str, side: str, quantity: float
    ) -> dict | None:
        """成行注文を処理する"""
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
    ) -> dict | None:
        """指値注文を処理する

        翌バーのhigh/lowで約定判定:
        - 買い指値: limit_price >= low なら約定（limit_priceで約定）
        - 売り指値: limit_price <= high なら約定（limit_priceで約定）
        - 同値（limit_price == high/low）は未約定とする
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
        """
        # 共通バリデーションヘルパーを使用
        self._validate_orders(orders)

        fills_data: list[dict] = []

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
        filtered = all_fills.filter(
            (pl.col("timestamp") >= start) & (pl.col("timestamp") <= end)
        )

        if filtered.height == 0:
            return pl.DataFrame(schema=FillReportSchema.REQUIRED_COLUMNS)

        return self._validate_fills(filtered)

    def fetch_positions(self) -> pl.DataFrame:
        """約定履歴から現在のポジションを計算する

        ショートポジション（マイナス数量）を許容。
        平均取得単価はロングなら買いの加重平均、ショートなら売りの加重平均。
        """
        if not self.fill_history:
            return pl.DataFrame(schema=PositionSchema.REQUIRED_COLUMNS)

        all_fills = pl.concat(self.fill_history)

        # ポジションを累積計算（加重平均価格を計算）
        positions = (
            all_fills
            .with_columns([
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
            ])
            .group_by("symbol")
            .agg([
                pl.col("signed_quantity").sum().alias("quantity"),
                pl.col("buy_value").sum().alias("total_buy_value"),
                pl.col("buy_quantity").sum().alias("total_buy_quantity"),
                pl.col("sell_value").sum().alias("total_sell_value"),
                pl.col("sell_quantity").sum().alias("total_sell_quantity"),
            ])
            .filter(pl.col("quantity") != 0)
            .with_columns([
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
            ])
            .select(["symbol", "quantity", "avg_price"])
        )

        return self._validate_positions(positions)
```

### 実運用用API実装（ユーザ実装例）

```python
from qeel.exchange_clients import BaseExchangeClient
from qeel.utils.notification import send_slack_notification
from qeel.utils.retry import with_retry
from qeel.utils.rounding import round_to_unit


class ExchangeAPIClient(BaseExchangeClient):
    """取引所API呼び出し実装（qeel.utils使用例）

    qeel.utilsが提供するリトライ・通知・丸め機能を利用して、
    エラーハンドリングと取引所仕様への適合を簡潔に実装する。
    """

    def __init__(
        self,
        api_client,
        slack_webhook_url: str | None = None,
        tick_size: float = 0.01,
        lot_size: float = 1.0,
    ):
        self.api_client = api_client
        self.submitted_order_ids: list[str] = []
        self.slack_webhook_url = slack_webhook_url
        self.tick_size = tick_size
        self.lot_size = lot_size

    def submit_orders(self, orders: pl.DataFrame) -> None:
        # 共通バリデーションヘルパーを使用
        self._validate_orders(orders)

        # 取引所APIに注文を送信（with_retryでexponential backoff）
        for row in orders.iter_rows(named=True):
            try:
                # 取引所仕様に応じて数量・価格を丸める
                rounded_price = round_to_unit(row["price"], self.tick_size) if row["price"] is not None else None
                rounded_quantity = round_to_unit(row["quantity"], self.lot_size)

                order_id = with_retry(
                    func=lambda: self.api_client.submit_order(
                        symbol=row["symbol"],
                        side=row["side"],
                        quantity=rounded_quantity,
                        price=rounded_price,
                        order_type=row["order_type"],
                    ),
                    max_attempts=3,
                    timeout=10.0,
                    backoff_factor=2.0,
                )
                self.submitted_order_ids.append(order_id)
            except Exception as e:
                # Slack通知（オプション）
                if self.slack_webhook_url:
                    send_slack_notification(
                        webhook_url=self.slack_webhook_url,
                        message=f"注文送信エラー: {e}",
                        level="error",
                    )
                raise RuntimeError(f"注文送信エラー: {e}")

    def fetch_fills(self, start: datetime, end: datetime) -> pl.DataFrame:
        """指定期間の約定情報をAPIから取得する

        Args:
            start: 取得開始日時
            end: 取得終了日時

        Returns:
            期間内の約定情報（FillReportSchema準拠）
        """
        try:
            # 取引所APIから期間指定で約定履歴を取得
            fills_response = with_retry(
                func=lambda: self.api_client.get_fills(start=start, end=end),
                max_attempts=3,
                timeout=10.0,
                backoff_factor=2.0,
            )

            if not fills_response:
                return pl.DataFrame(schema=FillReportSchema.REQUIRED_COLUMNS)

            fills_data = [
                {
                    "order_id": fill.order_id,
                    "symbol": fill.symbol,
                    "side": fill.side,
                    "filled_quantity": fill.filled_quantity,
                    "filled_price": fill.filled_price,
                    "commission": fill.commission,
                    "timestamp": fill.timestamp,
                }
                for fill in fills_response
            ]

            fills = pl.DataFrame(fills_data)

            # 共通バリデーションヘルパーを使用
            return self._validate_fills(fills)

        except Exception as e:
            if self.slack_webhook_url:
                send_slack_notification(
                    webhook_url=self.slack_webhook_url,
                    message=f"約定情報取得エラー: {e}",
                    level="error",
                )
            raise RuntimeError(f"約定情報取得エラー: {e}")

    def fetch_positions(self) -> pl.DataFrame:
        """取引所APIからポジションを取得"""
        try:
            positions_data = with_retry(
                func=lambda: self.api_client.get_positions(),
                max_attempts=3,
                timeout=10.0,
                backoff_factor=2.0,
            )

            # API response を PositionSchema に変換
            positions = pl.DataFrame([
                {
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "avg_price": pos.avg_price,
                }
                for pos in positions_data
            ])

            # 共通バリデーションヘルパーを使用
            return self._validate_positions(positions)
        except Exception as e:
            if self.slack_webhook_url:
                send_slack_notification(
                    webhook_url=self.slack_webhook_url,
                    message=f"ポジション情報取得エラー: {e}",
                    level="error",
                )
            raise RuntimeError(f"ポジション情報取得エラー: {e}")
```

## 契約事項

### submit_orders

- 入力: `OrderSchema` に準拠したDataFrame（symbol, side, quantity, price, order_type）
- バックテスト: モックで約定処理（成行/指値に対応）
- 実運用: 取引所APIに送信（非同期処理可）

### fetch_fills

- 入力: `start: datetime`, `end: datetime`（取得期間）
- 出力: `FillReportSchema` に準拠したDataFrame
- バックテスト: `fill_history`から期間でフィルタして返す
- 実運用: 取引所APIから期間指定で約定履歴を取得

### fetch_positions

- 出力: `PositionSchema` に準拠したDataFrame
- バックテスト: 約定履歴から計算した現在のポジションを返す
- 実運用: 取引所APIから現在のポジションを取得
- **ショートポジション対応**: 売り約定が買い約定を上回る場合、負の数量（マイナス）で表現。数量ゼロのポジションは除外
- **平均取得単価**: ロング（正の数量）は買いの加重平均、ショート（負の数量）は売りの加重平均

### MockExchangeClient固有メソッド

モック実装には以下のセットアップメソッドが必要:

- `__init__(config, ohlcv_data_source)`: コスト設定とOHLCVデータソースを受け取る
- `load_ohlcv(start, end, symbols)`: バックテスト開始時にOHLCVデータをキャッシュ
- `set_current_datetime(dt: datetime)`: 現在のiteration日時を設定

**初期化フロー**:
1. BacktestRunnerが`MockExchangeClient(config, ohlcv_data_source)`で初期化
2. バックテスト開始時に`load_ohlcv(start, end, symbols)`でOHLCVをキャッシュ
3. 各iterationで`set_current_datetime(dt)`を呼び出し

### 成行注文の約定ロジック（バックテスト）

- **約定価格**: `CostConfig.market_fill_price_type`で選択
  - `"next_open"`: 翌バーの始値で約定（デフォルト、より現実的）
  - `"current_close"`: 当バーの終値で約定
- **スリッページ**: 買いは+（高く買う）、売りは-（安く売る）
- **約定時刻**: 参照したバーのdatetime

### 指値注文の約定ロジック（バックテスト）

- **約定判定**: 翌バーのhigh/lowで判定
  - 買い指値: `limit_price > low` なら約定
  - 売り指値: `limit_price < high` なら約定
  - 同値（`limit_price == low` または `limit_price == high`）は**未約定**
- **約定価格**: 指値価格そのもの（スリッページなし）
- **約定時刻**: 翌バーのdatetime

### 手数料計算

- **計算式**: `filled_price * filled_quantity * commission_rate`
- **タイミング**: 約定価格確定後に計算（注文価格ではなく約定価格ベース）

### エラーハンドリング

- **バックテスト**: 基本的にエラーは発生しない（スキーマエラー、OHLCVデータ未設定時のみ）
- **実運用**: APIエラーはユーザがcatch & handleする責任
  - ユーザは`qeel.utils.retry`（exponential backoff、タイムアウト）と`qeel.utils.notification`（Slack通知等）を自由に利用可能
  - utilsの利用は任意であり、ユーザは独自の実装も可能
  - リトライロジック、レート制限対策、通知などの実装はユーザ責任

### 数量・価格の丸め

- **バックテスト**: 丸めをスキップ（理想的な約定を想定）
- **実運用**: `submit_orders()` 内で取引所仕様に応じて丸め処理を実施

## テスタビリティ

- `MockExchangeClient` をテストで使用し、約定ロジックとポジション計算を検証
- 実運用実装は、モックAPIクライアントでユニットテスト可能
