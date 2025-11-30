# Contract: BasePortfolioConstructor

## 概要

ユーザがシグナルからポートフォリオを構築するロジックを実装するための抽象基底クラス。銘柄選定と執行条件の前処理（メタデータ付与）を同時に行い、`OrderCreator`に渡す。Pydanticモデルでパラメータを定義し、ABCパターンで拡張性を確保する。

## インターフェース定義

```python
from abc import ABC, abstractmethod
import polars as pl
from pydantic import BaseModel

class PortfolioConstructorParams(BaseModel):
    """ポートフォリオ構築パラメータの基底クラス

    ユーザはこれを継承して独自のパラメータを定義する。
    """
    pass  # ユーザが拡張


class BasePortfolioConstructor(ABC):
    """ポートフォリオ構築抽象基底クラス

    ユーザはこのクラスを継承し、construct()メソッドを実装する。

    Attributes:
        params: PortfolioConstructorParams（Pydanticモデル）
    """

    def __init__(self, params: PortfolioConstructorParams):
        """
        Args:
            params: ポートフォリオ構築パラメータ（Pydanticモデル）
        """
        self.params = params

    @abstractmethod
    def construct(self, signals: pl.DataFrame, current_positions: pl.DataFrame) -> pl.DataFrame:
        """シグナルからポートフォリオを構築し、執行条件計算に必要なメタデータを含むDataFrameを返す

        Args:
            signals: シグナルDataFrame（SignalSchema準拠）
            current_positions: 現在のポジション（PositionSchema準拠）

        Returns:
            構築済みポートフォリオDataFrame（PortfolioSchema準拠）
            必須列: datetime, symbol
            オプション列: signal_strength, priority, tags等（ユーザ定義）

        Raises:
            ValueError: シグナルが不正またはスキーマ違反の場合
        """
        ...
```

## デフォルト実装例（TopNPortfolioConstructor）

```python
from pydantic import Field

class TopNConstructorParams(PortfolioConstructorParams):
    """上位N銘柄構築のパラメータ"""
    top_n: int = Field(default=10, gt=0, description="選定する銘柄数")
    ascending: bool = Field(default=False, description="昇順ソート（Falseの場合、シグナル大きい順）")


class TopNPortfolioConstructor(BasePortfolioConstructor):
    """シグナル上位N銘柄でポートフォリオを構築するデフォルト実装

    シグナル値でソートし、上位N銘柄を選定する。
    選定された銘柄のシグナル強度（signal列）をメタデータとして含めて返す。
    """

    def construct(self, signals: pl.DataFrame, current_positions: pl.DataFrame) -> pl.DataFrame:
        from qeel.schemas import SignalSchema, PositionSchema, PortfolioSchema

        # スキーマバリデーション
        SignalSchema.validate(signals)
        PositionSchema.validate(positions)

        # シグナルでソートして上位N銘柄を選定
        portfolio = (
            signals
            .sort("signal", descending=not self.params.ascending)
            .head(self.params.top_n)
            .select(["datetime", "symbol", "signal"])
            .rename({"signal": "signal_strength"})
        )

        return PortfolioSchema.validate(portfolio)
```

## カスタム実装例（閾値フィルタ付き）

```python
class ThresholdConstructorParams(PortfolioConstructorParams):
    """閾値フィルタ付き構築のパラメータ"""
    top_n: int = Field(default=10, gt=0)
    min_signal_threshold: float = Field(default=0.0, description="最小シグナル閾値")


class ThresholdPortfolioConstructor(BasePortfolioConstructor):
    """シグナルが閾値以上の銘柄から上位N銘柄でポートフォリオを構築"""

    def construct(self, signals: pl.DataFrame, current_positions: pl.DataFrame) -> pl.DataFrame:
        from qeel.schemas import SignalSchema, PositionSchema, PortfolioSchema

        SignalSchema.validate(signals)
        PositionSchema.validate(positions)

        # 閾値フィルタ + 上位N選定 + メタデータ付与
        portfolio = (
            signals
            .filter(pl.col("signal") >= self.params.min_signal_threshold)
            .sort("signal", descending=True)
            .head(self.params.top_n)
            .select(["datetime", "symbol", "signal"])
            .rename({"signal": "signal_strength"})
        )

        return PortfolioSchema.validate(portfolio)
```

## 複数シグナル対応の実装例

```python
class MultiSignalConstructorParams(PortfolioConstructorParams):
    """複数シグナルを組み合わせた構築のパラメータ"""
    top_n: int = Field(default=10, gt=0)
    momentum_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    value_weight: float = Field(default=0.5, ge=0.0, le=1.0)


class MultiSignalPortfolioConstructor(BasePortfolioConstructor):
    """複数シグナルを組み合わせてポートフォリオを構築

    signal_momentum と signal_value を重み付けして合成シグナルを作成し、
    上位N銘柄を選定する。
    """

    def construct(self, signals: pl.DataFrame, current_positions: pl.DataFrame) -> pl.DataFrame:
        from qeel.schemas import SignalSchema, PositionSchema, PortfolioSchema

        SignalSchema.validate(signals)
        PositionSchema.validate(positions)

        # 複数シグナルの重み付け合成
        portfolio = (
            signals
            .with_columns([
                (
                    pl.col("signal_momentum") * self.params.momentum_weight +
                    pl.col("signal_value") * self.params.value_weight
                ).alias("composite_signal")
            ])
            .sort("composite_signal", descending=True)
            .head(self.params.top_n)
            .select([
                "datetime",
                "symbol",
                "composite_signal",
                "signal_momentum",  # メタデータとして保持
                "signal_value"      # メタデータとして保持
            ])
            .rename({"composite_signal": "signal_strength"})
        )

        return PortfolioSchema.validate(portfolio)
```

## 契約事項

### 入力

- `signals`: SignalSchemaに準拠したPolars DataFrame（必須列: datetime, symbol; オプション列: signal, signal_momentum等の任意のシグナル列）
- `current_positions`: PositionSchemaに準拠したPolars DataFrame（現在のポジション情報）

### 出力

- 構築済みポートフォリオDataFrame（PortfolioSchemaに準拠）
  - 必須列: `datetime` (pl.Datetime), `symbol` (pl.Utf8)
  - オプション列: `signal_strength` (pl.Float64), `priority` (pl.Int64), `tags` (pl.Utf8) 等、ユーザが任意に定義可能
- 銘柄が1つも選定されない場合は空のDataFrameを返す（エラーにしない）
- `OrderCreator`がメタデータを参照して柔軟な注文生成を実装できる

### パラメータ管理

- すべてのパラメータはPydanticモデル（`PortfolioConstructorParams`を継承）で定義する
- パラメータは実行時にバリデーションされる
- 型ヒント必須（Constitution IV: 型安全性の確保）

### テスタビリティ

- モックシグナルデータで容易にテスト可能
- パラメータを変更して異なる振る舞いを検証可能

## 使用例

```python
from qeel.portfolio_constructors import TopNPortfolioConstructor, TopNConstructorParams

# パラメータ定義
params = TopNConstructorParams(top_n=10)

# コンストラクタインスタンス化
constructor = TopNPortfolioConstructor(params=params)

# バックテストエンジンに渡す
engine = BacktestEngine(
    calculator=signal_calculator,
    portfolio_constructor=constructor,  # デフォルトまたはカスタム実装
    order_creator=order_creator,
    data_sources=data_sources,
    executor=executor,
    context_store=context_store,
    config=config,
)
```

## 標準実装

Qeelは以下の標準実装を提供する：

- `TopNPortfolioConstructor`: シグナル上位N銘柄でポートフォリオ構築（**推奨デフォルト実装**）
  - パラメータ: `top_n`（選定数）、`ascending`（ソート順）

ユーザは独自のコンストラクタを自由に実装可能。
