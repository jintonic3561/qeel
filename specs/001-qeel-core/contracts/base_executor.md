# Contract: BaseExecutor

## 概要

注文の執行と約定情報の取得を抽象化するインターフェース。バックテスト時はモック、実運用時は取引所APIを使用する。

## インターフェース定義

```python
from abc import ABC, abstractmethod
import polars as pl

class BaseExecutor(ABC):
    """執行抽象基底クラス

    バックテストではモック約定、実運用では取引所API呼び出しを実装する。
    """

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
```

## 実装例

### Backtest用モック実装

```python
from qeel.executors import BaseExecutor
from qeel.schemas import OrderSchema, FillReportSchema
from qeel.config import CostConfig
import polars as pl
from datetime import datetime
import uuid

class MockExecutor(BaseExecutor):
    """バックテスト用モック執行

    全注文を即座に約定させ、コスト設定に基づいて手数料・スリッページを適用する。
    """

    def __init__(self, config: CostConfig):
        self.config = config
        self.pending_fills: list[pl.DataFrame] = []

    def submit_orders(self, orders: pl.DataFrame) -> None:
        OrderSchema.validate(orders)

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

    def fetch_fills(self) -> pl.DataFrame:
        if not self.pending_fills:
            return pl.DataFrame(schema=FillReportSchema.REQUIRED_COLUMNS)

        # すべての約定を返す
        all_fills = pl.concat(self.pending_fills)
        self.pending_fills.clear()
        return FillReportSchema.validate(all_fills)
```

### 実運用用API実装（ユーザ実装例）

```python
class ExchangeAPIExecutor(BaseExecutor):
    """取引所API呼び出し実装

    ユーザが独自に実装。エラーハンドリングもユーザ責任。
    """

    def __init__(self, api_client):
        self.api_client = api_client
        self.submitted_order_ids: list[str] = []

    def submit_orders(self, orders: pl.DataFrame) -> None:
        OrderSchema.validate(orders)

        # 取引所APIに注文を送信
        for row in orders.iter_rows(named=True):
            try:
                order_id = self.api_client.submit_order(
                    symbol=row["symbol"],
                    side=row["side"],
                    quantity=row["quantity"],
                    price=row["price"],
                    order_type=row["order_type"],
                )
                self.submitted_order_ids.append(order_id)
            except Exception as e:
                # エラーハンドリングはユーザ責任
                # リトライ、ログ、通知などを実装
                raise RuntimeError(f"注文送信エラー: {e}")

    def fetch_fills(self) -> pl.DataFrame:
        # 約定情報をAPIから取得
        fills_data = []
        for order_id in self.submitted_order_ids:
            try:
                fill = self.api_client.get_fill(order_id)
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
                raise RuntimeError(f"約定情報取得エラー: {e}")

        self.submitted_order_ids.clear()

        if not fills_data:
            return pl.DataFrame(schema=FillReportSchema.REQUIRED_COLUMNS)

        fills_df = pl.DataFrame(fills_data)
        return FillReportSchema.validate(fills_df)
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

### エラーハンドリング

- **バックテスト**: 基本的にエラーは発生しない（スキーマエラーのみ）
- **実運用**: APIエラーはユーザがcatch & handleする責任
  - リトライロジック
  - タイムアウト処理
  - レート制限対策
  - 通知（Slack/Email等）

### 数量・価格の丸め

- **バックテスト**: 丸めをスキップ（理想的な約定を想定）
- **実運用**: `submit_orders()` 内で取引所仕様に応じて丸め処理を実施

## テスタビリティ

- `MockExecutor` をテストで使用し、約定ロジックを検証
- 実運用実装は、モックAPIクライアントでユニットテスト可能
