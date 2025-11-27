# Contract: BaseSymbolSelector

## 概要

ユーザがシグナルから銘柄を選定するロジックを実装するための抽象基底クラス。Signal計算クラスと同様に、Pydanticモデルでパラメータを定義し、ABCパターンで拡張性を確保する。

## インターフェース定義

```python
from abc import ABC, abstractmethod
import polars as pl
from pydantic import BaseModel

class SymbolSelectorParams(BaseModel):
    """銘柄選定パラメータの基底クラス

    ユーザはこれを継承して独自のパラメータを定義する。
    """
    pass  # ユーザが拡張


class BaseSymbolSelector(ABC):
    """銘柄選定抽象基底クラス

    ユーザはこのクラスを継承し、select()メソッドを実装する。

    Attributes:
        params: SymbolSelectorParams（Pydanticモデル）
    """

    def __init__(self, params: SymbolSelectorParams):
        """
        Args:
            params: 銘柄選定パラメータ（Pydanticモデル）
        """
        self.params = params

    @abstractmethod
    def select(self, signals: pl.DataFrame, context: dict) -> list[str]:
        """シグナルから銘柄を選定する

        Args:
            signals: シグナルDataFrame（SignalSchema準拠）
            context: コンテキスト情報（ポジション、選定履歴等）

        Returns:
            選定された銘柄コードのリスト

        Raises:
            ValueError: シグナルが不正またはスキーマ違反の場合
        """
        ...
```

## デフォルト実装例（TopNSymbolSelector）

```python
from pydantic import Field

class TopNSelectorParams(SymbolSelectorParams):
    """上位N銘柄選定のパラメータ"""
    top_n: int = Field(default=10, gt=0, description="選定する銘柄数")
    ascending: bool = Field(default=False, description="昇順ソート（Falseの場合、シグナル大きい順）")


class TopNSymbolSelector(BaseSymbolSelector):
    """シグナル上位N銘柄を選定するデフォルト実装

    シグナル値でソートし、上位N銘柄を選定する。
    """

    def select(self, signals: pl.DataFrame, context: dict) -> list[str]:
        from qeel.schemas import SignalSchema

        # スキーマバリデーション
        SignalSchema.validate(signals)

        # シグナルでソートして上位N銘柄を選定
        return (
            signals
            .sort("signal", descending=not self.params.ascending)
            .head(self.params.top_n)
            ["symbol"]
            .to_list()
        )
```

## カスタム実装例（閾値フィルタ付き）

```python
class ThresholdSelectorParams(SymbolSelectorParams):
    """閾値フィルタ付き選定のパラメータ"""
    top_n: int = Field(default=10, gt=0)
    min_signal_threshold: float = Field(default=0.0, description="最小シグナル閾値")


class ThresholdSymbolSelector(BaseSymbolSelector):
    """シグナルが閾値以上の銘柄から上位N銘柄を選定"""

    def select(self, signals: pl.DataFrame, context: dict) -> list[str]:
        from qeel.schemas import SignalSchema

        SignalSchema.validate(signals)

        # 閾値フィルタ + 上位N選定
        return (
            signals
            .filter(pl.col("signal") >= self.params.min_signal_threshold)
            .sort("signal", descending=True)
            .head(self.params.top_n)
            ["symbol"]
            .to_list()
        )
```

## 契約事項

### 入力

- `signals`: SignalSchemaに準拠したPolars DataFrame（必須列: datetime, symbol, signal）
- `context`: コンテキスト情報（ポジション、選定履歴等）、dict形式

### 出力

- 選定された銘柄コードのリスト（`list[str]`）
- 銘柄が1つも選定されない場合は空リストを返す（エラーにしない）

### パラメータ管理

- すべてのパラメータはPydanticモデル（`SymbolSelectorParams`を継承）で定義する
- パラメータは実行時にバリデーションされる
- 型ヒント必須（Constitution IV: 型安全性の確保）

### テスタビリティ

- モックシグナルデータで容易にテスト可能
- パラメータを変更して異なる振る舞いを検証可能

## 使用例

```python
from qeel.selectors import TopNSymbolSelector, TopNSelectorParams

# パラメータ定義
params = TopNSelectorParams(top_n=10)

# セレクタインスタンス化
selector = TopNSymbolSelector(params=params)

# バックテストエンジンに渡す
engine = BacktestEngine(
    calculator=signal_calculator,
    symbol_selector=selector,  # デフォルトまたはカスタム実装
    order_creator=order_creator,
    data_sources=data_sources,
    executor=executor,
    context_store=context_store,
    config=config,
)
```

## 標準実装

Qeelは以下の標準実装を提供する：

- `TopNSymbolSelector`: シグナル上位N銘柄選定（**推奨デフォルト実装**）
  - パラメータ: `top_n`（選定数）、`ascending`（ソート順）

ユーザは独自のセレクタを自由に実装可能。
