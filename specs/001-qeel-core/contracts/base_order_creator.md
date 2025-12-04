# Contract: BaseOrderCreator

## 概要

ユーザがポートフォリオ計画（選定銘柄+メタデータ）とポジションから注文を生成するロジックを実装するための抽象基底クラス。Pydanticモデルでパラメータを定義し、ABCパターンで拡張性を確保する。入力バリデーションは共通ヘルパーメソッドとして提供され、重複を避けて可読性を向上させる。

## インターフェース定義

```python
from abc import ABC, abstractmethod

import polars as pl
from pydantic import BaseModel

from qeel.schemas import PortfolioSchema, PositionSchema, OHLCVSchema


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

    def _validate_inputs(
        self,
        portfolio_plan: pl.DataFrame,
        current_positions: pl.DataFrame,
        ohlcv: pl.DataFrame,
    ) -> None:
        """入力データの共通バリデーション

        サブクラスで任意に呼び出し可能なヘルパーメソッド。
        スキーマバリデーションを一箇所で実行し、重複を避ける。

        Args:
            portfolio_plan: 構築済みポートフォリオDataFrame（PortfolioSchema準拠）
            current_positions: 現在のポジション（PositionSchema準拠）
            ohlcv: OHLCV価格データ（OHLCVSchema準拠）

        Raises:
            ValueError: スキーマ違反の場合
        """

        PortfolioSchema.validate(portfolio_plan)
        PositionSchema.validate(current_positions)
        OHLCVSchema.validate(ohlcv)

    @abstractmethod
    def create(
        self,
        portfolio_plan: pl.DataFrame,
        current_positions: pl.DataFrame,
        ohlcv: pl.DataFrame,
    ) -> pl.DataFrame:
        """ポートフォリオ計画とポジションから注文を生成する

        Args:
            portfolio_plan: 構築済みポートフォリオDataFrame（PortfolioSchema準拠、メタデータ含む）
                必須列: datetime, symbol
                オプション列: signal_strength, priority, tags等（PortfolioConstructorから渡される）
            current_positions: 現在のポジション（PositionSchema準拠）
            ohlcv: OHLCV価格データ（OHLCVSchema準拠、価格情報取得用）

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
        portfolio_plan: pl.DataFrame,
        current_positions: pl.DataFrame,
        ohlcv: pl.DataFrame,
    ) -> pl.DataFrame:
        from qeel.schemas import OrderSchema

        # 共通バリデーションヘルパーを使用
        self._validate_inputs(portfolio_plan, current_positions, ohlcv)

        if portfolio_plan.height == 0:
            return pl.DataFrame(schema=OrderSchema.REQUIRED_COLUMNS)

        n_symbols = portfolio_plan.height
        target_value_per_symbol = self.params.capital / n_symbols

        orders = []
        for row in portfolio_plan.iter_rows(named=True):
            symbol = row["symbol"]

            # 現在価格取得（open価格）
            price_row = ohlcv.filter(pl.col("symbol") == symbol)
            if price_row.height == 0:
                continue  # データがない銘柄はスキップ

            current_price = price_row["open"][0]
            target_quantity = target_value_per_symbol / current_price

            # シグナル強度をportfolio_planから取得（メタデータとして含まれている）
            if "signal_strength" in portfolio_plan.columns:
                signal_value = row["signal_strength"]
            else:
                signal_value = 1.0  # デフォルト値

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
        portfolio_plan: pl.DataFrame,
        current_positions: pl.DataFrame,
        ohlcv: pl.DataFrame,
    ) -> pl.DataFrame:
        from qeel.schemas import OrderSchema

        # 共通バリデーションヘルパーを使用
        self._validate_inputs(portfolio_plan, current_positions, ohlcv)

        if portfolio_plan.height == 0:
            return pl.DataFrame(schema=OrderSchema.REQUIRED_COLUMNS)

        orders = []
        max_value_per_symbol = self.params.capital * self.params.max_position_pct

        for row in portfolio_plan.iter_rows(named=True):
            symbol = row["symbol"]

            price_row = ohlcv.filter(pl.col("symbol") == symbol)
            if price_row.height == 0:
                continue

            current_price = price_row["close"][0]

            # シグナルの強さをportfolio_planから取得（メタデータとして含まれている）
            if "signal_strength" in portfolio_plan.columns:
                signal_value = row["signal_strength"]
            else:
                signal_value = 1.0  # デフォルト値

            # リスクに応じた配分（シグナルの強さに応じて数量を調整）
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

- `portfolio_plan`: 構築済みポートフォリオDataFrame（PortfolioSchema準拠、メタデータ含む）
  - 必須列: `datetime`, `symbol`
  - オプション列: `signal_strength`, `priority`, `tags` 等（`PortfolioConstructor`から渡される）
- `current_positions`: PositionSchemaに準拠したPolars DataFrame
- `ohlcv`: OHLCVSchemaに準拠したPolars DataFrame（価格情報取得用）

### 出力

- 注文DataFrame（OrderSchemaに準拠）
- 注文が1つも生成されない場合は空のDataFrameを返す（エラーにしない）

### パラメータ管理

- すべてのパラメータはPydanticモデル（`OrderCreatorParams`を継承）で定義する
- パラメータは実行時にバリデーションされる
- 型ヒント必須（Constitution IV: 型安全性の確保）

### スキーマバリデーション

- 入力DataFrameのバリデーションには、`BaseOrderCreator._validate_inputs()`ヘルパーメソッドを使用可能（推奨）
- ユーザは独自のバリデーションロジックを実装することも可能
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
