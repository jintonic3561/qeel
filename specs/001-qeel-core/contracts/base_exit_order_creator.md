# Contract: BaseExitOrderCreator

## 概要

ユーザが現在のポジションと価格データからエグジット注文を生成するロジックを実装するための抽象基底クラス。Pydanticモデルでパラメータを定義し、ABCパターンで拡張性を確保する。入力バリデーションは共通ヘルパーメソッドとして提供され、重複を避けて可読性を向上させる。

## インターフェース定義

```python
from abc import ABC, abstractmethod

import polars as pl
from pydantic import BaseModel

from qeel.schemas import PositionSchema, OHLCVSchema


class ExitOrderCreatorParams(BaseModel):
    """エグジット注文生成パラメータの基底クラス

    ユーザはこれを継承して独自のパラメータを定義する。
    """
    pass  # ユーザが拡張


class BaseExitOrderCreator(ABC):
    """エグジット注文生成抽象基底クラス

    ユーザはこのクラスを継承し、create()メソッドを実装する。

    Attributes:
        params: ExitOrderCreatorParams（Pydanticモデル）
    """

    def __init__(self, params: ExitOrderCreatorParams):
        """
        Args:
            params: エグジット注文生成パラメータ（Pydanticモデル）
        """
        self.params = params

    def _validate_inputs(
        self,
        current_positions: pl.DataFrame,
        ohlcv: pl.DataFrame,
    ) -> None:
        """入力データの共通バリデーション

        サブクラスで任意に呼び出し可能なヘルパーメソッド。
        スキーマバリデーションを一箇所で実行し、重複を避ける。

        Args:
            current_positions: 現在のポジション（PositionSchema準拠）
            ohlcv: OHLCV価格データ（OHLCVSchema準拠）

        Raises:
            ValueError: スキーマ違反の場合
        """

        PositionSchema.validate(current_positions)
        OHLCVSchema.validate(ohlcv)

    @abstractmethod
    def create(
        self,
        current_positions: pl.DataFrame,
        ohlcv: pl.DataFrame,
    ) -> pl.DataFrame:
        """現在のポジションと価格データからエグジット注文を生成する

        Args:
            current_positions: 現在のポジション（PositionSchema準拠）
            ohlcv: OHLCV価格データ（OHLCVSchema準拠、価格情報取得用）

        Returns:
            エグジット注文DataFrame（OrderSchema準拠）

        Raises:
            ValueError: 入力データが不正またはスキーマ違反の場合
        """
        ...
```

## デフォルト実装例（FullExitOrderCreator）

```python
from pydantic import Field


class FullExitParams(ExitOrderCreatorParams):
    """全ポジション決済のパラメータ"""
    exit_threshold: float = Field(default=1.0, ge=0.0, le=1.0, description="エグジット閾値（保有比率）")


class FullExitOrderCreator(BaseExitOrderCreator):
    """保有ポジションの全決済注文を生成するデフォルト実装

    保有している全銘柄に対して、成行決済注文を生成する。
    ohlcvは利用可能だが、この実装では使用しない。
    """

    def create(
        self,
        current_positions: pl.DataFrame,
        ohlcv: pl.DataFrame,
    ) -> pl.DataFrame:
        from qeel.schemas import OrderSchema

        # 共通バリデーションヘルパーを使用
        self._validate_inputs(current_positions, ohlcv)

        if current_positions.height == 0:
            return pl.DataFrame(schema=OrderSchema.REQUIRED_COLUMNS)

        orders = []
        for row in current_positions.iter_rows(named=True):
            symbol = row["symbol"]
            quantity = row["quantity"]

            if quantity == 0:
                continue  # ポジションがゼロの場合はスキップ

            # exit_thresholdに応じて決済数量を調整
            exit_quantity = abs(quantity) * self.params.exit_threshold

            # 買いポジションは売り、売りポジションは買いで決済
            side = "sell" if quantity > 0 else "buy"

            orders.append({
                "symbol": symbol,
                "side": side,
                "quantity": exit_quantity,
                "price": None,  # 成行
                "order_type": "market",
            })

        return OrderSchema.validate(pl.DataFrame(orders))
```

## カスタム実装例（条件付きエグジット）

```python
class ConditionalExitParams(ExitOrderCreatorParams):
    """条件付きエグジットのパラメータ"""
    stop_loss_pct: float = Field(default=0.05, gt=0.0, le=1.0, description="ストップロス閾値（%）")
    take_profit_pct: float = Field(default=0.10, gt=0.0, le=1.0, description="テイクプロフィット閾値（%）")


class ConditionalExitOrderCreator(BaseExitOrderCreator):
    """条件付きエグジット注文を生成

    各ポジションの損益がストップロスまたはテイクプロフィット閾値に達した場合に決済注文を生成する。
    """

    def create(
        self,
        current_positions: pl.DataFrame,
        ohlcv: pl.DataFrame,
    ) -> pl.DataFrame:
        from qeel.schemas import OrderSchema

        # 共通バリデーションヘルパーを使用
        self._validate_inputs(current_positions, ohlcv)

        if current_positions.height == 0:
            return pl.DataFrame(schema=OrderSchema.REQUIRED_COLUMNS)

        orders = []
        for row in current_positions.iter_rows(named=True):
            symbol = row["symbol"]
            quantity = row["quantity"]
            avg_price = row["avg_price"]

            if quantity == 0:
                continue

            # 現在価格取得（close価格）
            price_row = ohlcv.filter(pl.col("symbol") == symbol)
            if price_row.height == 0:
                continue

            current_price = price_row["close"][0]

            # 損益率を計算
            if quantity > 0:  # 買いポジション
                pnl_pct = (current_price - avg_price) / avg_price
            else:  # 売りポジション
                pnl_pct = (avg_price - current_price) / avg_price

            # ストップロスまたはテイクプロフィット条件を満たす場合に決済
            should_exit = (
                pnl_pct <= -self.params.stop_loss_pct or
                pnl_pct >= self.params.take_profit_pct
            )

            if should_exit:
                side = "sell" if quantity > 0 else "buy"

                orders.append({
                    "symbol": symbol,
                    "side": side,
                    "quantity": abs(quantity),
                    "price": None,  # 成行
                    "order_type": "market",
                })

        return OrderSchema.validate(pl.DataFrame(orders))
```

## 契約事項

### 入力

- `current_positions`: PositionSchemaに準拠したPolars DataFrame
  - 必須列: `symbol`, `quantity`, `avg_price`
- `ohlcv`: OHLCVSchemaに準拠したPolars DataFrame（価格情報取得用）

### 出力

- エグジット注文DataFrame（OrderSchemaに準拠）
- 注文が1つも生成されない場合は空のDataFrameを返す（エラーにしない）

### パラメータ管理

- すべてのパラメータはPydanticモデル（`ExitOrderCreatorParams`を継承）で定義する
- パラメータは実行時にバリデーションされる
- 型ヒント必須（Constitution IV: 型安全性の確保）

### スキーマバリデーション

- 入力DataFrameのバリデーションには、`BaseExitOrderCreator._validate_inputs()`ヘルパーメソッドを使用可能（推奨）
- ユーザは独自のバリデーションロジックを実装することも可能
- 出力DataFrameは`OrderSchema.validate()`を通して返す

### テスタビリティ

- モックデータで容易にテスト可能
- パラメータを変更して異なる振る舞いを検証可能

## 使用例

```python
from qeel.exit_order_creators import FullExitOrderCreator, FullExitParams


# パラメータ定義
params = FullExitParams(exit_threshold=1.0)

# エグジット注文生成クラスのインスタンス化
exit_order_creator = FullExitOrderCreator(params=params)

# StrategyEngineに渡す
engine = StrategyEngine(
    calculator=signal_calculator,
    portfolio_constructor=portfolio_constructor,
    entry_order_creator=entry_order_creator,
    exit_order_creator=exit_order_creator,  # デフォルトまたはカスタム実装
    data_sources=data_sources,
    exchange_client=exchange_client,
    context_store=context_store,
    config=config,
)
```

## 標準実装

Qeelは以下の標準実装を提供する：

- `FullExitOrderCreator`: 全ポジション決済注文生成（**推奨デフォルト実装**）
  - パラメータ: `exit_threshold`（エグジット閾値、保有比率）

ユーザは独自のエグジット注文生成クラスを自由に実装可能。
