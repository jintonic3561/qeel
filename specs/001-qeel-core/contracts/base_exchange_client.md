# Contract: BaseExchangeClient

## 概要

注文の執行、約定情報の取得、ポジション情報の取得を抽象化するインターフェース。バックテスト時はモック、実運用時は取引所APIを使用する。

## インターフェース定義

```python
from abc import ABC, abstractmethod

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
    def fetch_fills(self) -> pl.DataFrame:
        """約定情報を取得する

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
from datetime import datetime

import polars as pl

from qeel.config import CostConfig
from qeel.exchange_clients import BaseExchangeClient
from qeel.schemas import FillReportSchema, OrderSchema, PositionSchema


class MockExchangeClient(BaseExchangeClient):
    """バックテスト用モック取引所クライアント

    全注文を即座に約定させ、コスト設定に基づいて手数料・スリッページを適用する。
    約定履歴から現在のポジションを計算して返す。
    """

    def __init__(self, config: CostConfig):
        self.config = config
        self.pending_fills: list[pl.DataFrame] = []
        self.fill_history: list[pl.DataFrame] = []  # ポジション計算用

    def submit_orders(self, orders: pl.DataFrame) -> None:
        # 共通バリデーションヘルパーを使用
        self._validate_orders(orders)

        # 全注文を即座に約定とみなす
        fills = orders.with_columns([
            pl.lit(str(uuid.uuid4())).alias("order_id"),
            pl.col("quantity").alias("filled_quantity"),
            # スリッページを適用
            (pl.col("price") * (1 + self.config.slippage_bps / 10000.0)).alias("filled_price"),
            # 手数料を計算
            (pl.col("quantity") * pl.col("price") * self.config.commission_rate).alias("commission"),
            pl.lit(datetime.now()).alias("timestamp"),
        ]).select([
            "order_id", "symbol", "side", "filled_quantity", "filled_price", "commission", "timestamp"
        ])

        self.pending_fills.append(fills)
        self.fill_history.append(fills)  # ポジション計算用に保持

    def fetch_fills(self) -> pl.DataFrame:
        if not self.pending_fills:
            return pl.DataFrame(schema=FillReportSchema.REQUIRED_COLUMNS)

        # すべての約定を返す
        all_fills = pl.concat(self.pending_fills)
        self.pending_fills.clear()

        # 共通バリデーションヘルパーを使用
        return self._validate_fills(all_fills)

    def fetch_positions(self) -> pl.DataFrame:
        """約定履歴から現在のポジションを計算"""
        if not self.fill_history:
            return pl.DataFrame(schema=PositionSchema.REQUIRED_COLUMNS)

        # fill_historyからポジションを累積計算
        all_fills = pl.concat(self.fill_history)
        positions = (
            all_fills
            .group_by("symbol")
            .agg([
                pl.when(pl.col("side") == "buy")
                  .then(pl.col("filled_quantity"))
                  .otherwise(-pl.col("filled_quantity"))
                  .sum()
                  .alias("quantity"),
                pl.col("filled_price").mean().alias("avg_price"),
            ])
            .filter(pl.col("quantity") != 0)
        )

        # 共通バリデーションヘルパーを使用
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

    def fetch_fills(self) -> pl.DataFrame:
        # 約定情報をAPIから取得（with_retryでexponential backoff）
        fills_data = []
        for order_id in self.submitted_order_ids:
            try:
                fill = with_retry(
                    func=lambda: self.api_client.get_fill(order_id),
                    max_attempts=3,
                    timeout=10.0,
                    backoff_factor=2.0,
                )
                fills_data.append({
                    "order_id": fill.order_id,
                    "symbol": fill.symbol,
                    "side": fill.side,
                    "filled_quantity": fill.filled_quantity,
                    "filled_price": fill.filled_price,
                    "commission": fill.commission,
                    "timestamp": fill.timestamp,
                })
            except Exception as e:
                if self.slack_webhook_url:
                    send_slack_notification(
                        webhook_url=self.slack_webhook_url,
                        message=f"約定情報取得エラー: {e}",
                        level="error",
                    )
                raise RuntimeError(f"約定情報取得エラー: {e}")

        self.submitted_order_ids.clear()

        if not fills_data:
            return pl.DataFrame(schema=FillReportSchema.REQUIRED_COLUMNS)

        fills = pl.DataFrame(fills_data)

        # 共通バリデーションヘルパーを使用
        return self._validate_fills(fills)

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

- 入力: `OrderSchema` に準拠したDataFrame
- バックテスト: モックで即座に約定処理
- 実運用: 取引所APIに送信（非同期処理可）

### fetch_fills

- 出力: `FillReportSchema` に準拠したDataFrame
- バックテスト: モック約定情報を返す
- 実運用: 実際の約定情報をAPIから取得

### fetch_positions

- 出力: `PositionSchema` に準拠したDataFrame
- バックテスト: 約定履歴から計算した現在のポジションを返す
- 実運用: 取引所APIから現在のポジションを取得

### エラーハンドリング

- **バックテスト**: 基本的にエラーは発生しない（スキーマエラーのみ）
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
