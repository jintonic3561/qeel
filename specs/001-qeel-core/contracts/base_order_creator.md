# Contract: BaseOrderCreator

## 概要

ユーザがシグナル、選定銘柄、ポジションから注文を生成するロジックを実装するための抽象基底クラス。Signal計算クラスと同様に、Pydanticモデルでパラメータを定義し、ABCパターンで拡張性を確保する。

## インターフェース定義

```python
from abc import ABC, abstractmethod
import polars as pl
from pydantic import BaseModel

class OrderCreatorParams(BaseModel):
    """注文生成パラメータの基底クラス

    ユーザはこれを継承して独自のパラメータを定義する。
    """
    pass  # ユーザが拡張


class BaseOrderCreator(ABC):
    """注文生成抽象基底クラス

    ユーザはこのクラスを継承し、create()メソッドを実装する。

    Attributes:
        params: OrderCreatorParams（Pydanticモデル）
    """

    def __init__(self, params: OrderCreatorParams):
        """
        Args:
            params: 注文生成パラメータ（Pydanticモデル）
        """
        self.params = params

    @abstractmethod
    def create(
        self,
        signals: pl.DataFrame,
        selected_symbols: list[str],
        positions: pl.DataFrame,
        market_data: pl.DataFrame,
    ) -> pl.DataFrame:
        """シグナルとポジションから注文を生成する

        Args:
            signals: シグナルDataFrame（SignalSchema準拠）
            selected_symbols: 選定された銘柄リスト
            positions: 現在のポジション（PositionSchema準拠）
            market_data: 市場データ（MarketDataSchema準拠、価格情報取得用）

        Returns:
            注文DataFrame（OrderSchema準拠）

        Raises:
            ValueError: 入力データが不正またはスキーマ違反の場合
        """
        ...
```

## デフォルト実装例（EqualWeightOrderCreator）

```python
from pydantic import Field

class EqualWeightParams(OrderCreatorParams):
    """等ウェイトポートフォリオのパラメータ"""
    capital: float = Field(default=1_000_000.0, gt=0.0, description="運用資金")
    rebalance_threshold: float = Field(default=0.05, ge=0.0, le=1.0, description="リバランス閾値")


class EqualWeightOrderCreator(BaseOrderCreator):
    """等ウェイトポートフォリオで注文を生成するデフォルト実装

    選定された銘柄に対して等ウェイト（1/N）で資金を配分し、
    open価格で成行注文を生成する。
    """

    def create(
        self,
        signals: pl.DataFrame,
        selected_symbols: list[str],
        positions: pl.DataFrame,
        market_data: pl.DataFrame,
    ) -> pl.DataFrame:
        from qeel.schemas import SignalSchema, PositionSchema, MarketDataSchema, OrderSchema

        # スキーマバリデーション
        SignalSchema.validate(signals)
        PositionSchema.validate(positions)
        MarketDataSchema.validate(market_data)

        n_symbols = len(selected_symbols)
        if n_symbols == 0:
            return pl.DataFrame(schema=OrderSchema.REQUIRED_COLUMNS)

        target_value_per_symbol = self.params.capital / n_symbols

        orders = []
        for symbol in selected_symbols:
            # 現在価格取得（open価格）
            price_row = market_data.filter(pl.col("symbol") == symbol)
            if price_row.height == 0:
                continue  # データがない銘柄はスキップ

            current_price = price_row["open"][0]
            target_quantity = target_value_per_symbol / current_price

            # シグナル取得
            signal_row = signals.filter(pl.col("symbol") == symbol)
            signal_value = signal_row["signal"][0] if signal_row.height > 0 else 0.0

            # シグナルが正なら買い、負なら売り
            side = "buy" if signal_value > 0 else "sell"

            orders.append({
                "symbol": symbol,
                "side": side,
                "quantity": abs(target_quantity),
                "price": None,  # 成行
                "order_type": "market",
            })

        return OrderSchema.validate(pl.DataFrame(orders))
```

## カスタム実装例（リスクパリティ）

```python
class RiskParityParams(OrderCreatorParams):
    """リスクパリティのパラメータ"""
    capital: float = Field(default=1_000_000.0, gt=0.0)
    max_position_pct: float = Field(default=0.2, gt=0.0, le=1.0, description="1銘柄の最大ポジション比率")
    volatility_window: int = Field(default=20, gt=0, description="ボラティリティ計算window")


class RiskParityOrderCreator(BaseOrderCreator):
    """リスクパリティに基づいて注文を生成

    各銘柄のボラティリティに応じて資金配分を調整する。
    """

    def create(
        self,
        signals: pl.DataFrame,
        selected_symbols: list[str],
        positions: pl.DataFrame,
        market_data: pl.DataFrame,
    ) -> pl.DataFrame:
        from qeel.schemas import SignalSchema, PositionSchema, MarketDataSchema, OrderSchema

        SignalSchema.validate(signals)
        PositionSchema.validate(positions)
        MarketDataSchema.validate(market_data)

        if len(selected_symbols) == 0:
            return pl.DataFrame(schema=OrderSchema.REQUIRED_COLUMNS)

        orders = []
        max_value_per_symbol = self.params.capital * self.params.max_position_pct

        for symbol in selected_symbols:
            price_row = market_data.filter(pl.col("symbol") == symbol)
            if price_row.height == 0:
                continue

            current_price = price_row["close"][0]

            # シグナルの強さに応じて数量計算
            signal_row = signals.filter(pl.col("symbol") == symbol)
            signal_value = signal_row["signal"][0] if signal_row.height > 0 else 0.0

            # リスクに応じた配分（ここでは簡略化してシグナルの強さで代用）
            target_value = max_value_per_symbol * abs(signal_value)
            quantity = target_value / current_price

            side = "buy" if signal_value > 0 else "sell"

            orders.append({
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": None,  # 成行
                "order_type": "market",
            })

        return OrderSchema.validate(pl.DataFrame(orders))
```

## 契約事項

### 入力

- `signals`: SignalSchemaに準拠したPolars DataFrame
- `selected_symbols`: 選定された銘柄リスト
- `positions`: PositionSchemaに準拠したPolars DataFrame
- `market_data`: MarketDataSchemaに準拠したPolars DataFrame（価格情報取得用）

### 出力

- 注文DataFrame（OrderSchemaに準拠）
- 注文が1つも生成されない場合は空のDataFrameを返す（エラーにしない）

### パラメータ管理

- すべてのパラメータはPydanticモデル（`OrderCreatorParams`を継承）で定義する
- パラメータは実行時にバリデーションされる
- 型ヒント必須（Constitution IV: 型安全性の確保）

### スキーマバリデーション

- 入力DataFrameは冒頭でスキーマバリデーションを実行する
- 出力DataFrameは`OrderSchema.validate()`を通して返す

### テスタビリティ

- モックデータで容易にテスト可能
- パラメータを変更して異なる振る舞いを検証可能

## 使用例

```python
from qeel.order_creators import EqualWeightOrderCreator, EqualWeightParams

# パラメータ定義
params = EqualWeightParams(capital=1_000_000.0, rebalance_threshold=0.05)

# 注文生成クラスのインスタンス化
order_creator = EqualWeightOrderCreator(params=params)

# バックテストエンジンに渡す
engine = BacktestEngine(
    calculator=signal_calculator,
    symbol_selector=symbol_selector,
    order_creator=order_creator,  # デフォルトまたはカスタム実装
    data_sources=data_sources,
    executor=executor,
    context_store=context_store,
    config=config,
)
```

## 標準実装

Qeelは以下の標準実装を提供する：

- `EqualWeightOrderCreator`: 等ウェイトポートフォリオ注文生成（**推奨デフォルト実装**）
  - パラメータ: `capital`（運用資金）、`rebalance_threshold`（リバランス閾値）

ユーザは独自の注文生成クラスを自由に実装可能。
