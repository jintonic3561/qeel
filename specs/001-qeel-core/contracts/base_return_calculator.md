# Contract: BaseReturnCalculator

## 概要

ユーザがリターン計算ロジックを実装するための抽象基底クラス。シグナル評価時に使用され、市場データを入力として受け取り、リターン系列を返す。

## インターフェース定義

```python
from abc import ABC, abstractmethod
import polars as pl
from qeel.schemas import ReturnCalculatorParams

class BaseReturnCalculator(ABC):
    """リターン計算抽象基底クラス

    シグナル評価（順位相関係数計算）時に使用される。

    Attributes:
        params: ReturnCalculatorParamsを継承したPydanticモデル
    """

    def __init__(self, params: ReturnCalculatorParams):
        """
        Args:
            params: リターン計算パラメータ（Pydanticモデル）
        """
        self.params = params

    def _validate_output(self, returns: pl.DataFrame) -> pl.DataFrame:
        """出力リターンの共通バリデーション

        サブクラスで任意に呼び出し可能なヘルパーメソッド。
        スキーマバリデーションを一箇所で実行し、重複を避ける。

        Args:
            returns: リターンDataFrame（必須列: datetime, symbol, return）

        Returns:
            バリデーション済みのDataFrame

        Raises:
            ValueError: スキーマ違反の場合
        """
        from qeel.schemas import ReturnSchema

        return ReturnSchema.validate(returns)

    @abstractmethod
    def calculate(self, market_data: pl.DataFrame) -> pl.DataFrame:
        """リターンを計算する

        Args:
            market_data: MarketDataSchemaに準拠したPolars DataFrame

        Returns:
            リターンDataFrame
            必須列: datetime (pl.Datetime), symbol (pl.Utf8), return (pl.Float64)

        Raises:
            ValueError: スキーマ不正の場合
        """
        ...
```

## 実装例

```python
from pydantic import BaseModel, Field
import polars as pl
from qeel.calculators.returns.base import BaseReturnCalculator

class LogReturnParams(BaseModel):
    period: int = Field(default=1, gt=0, description="リターン計算期間（日数）")

class LogReturnCalculator(BaseReturnCalculator):
    """対数リターン計算"""

    def calculate(self, market_data: pl.DataFrame) -> pl.DataFrame:
        returns = (
            market_data
            .sort(["symbol", "datetime"])
            .group_by("symbol")
            .agg([
                pl.col("datetime"),
                (pl.col("close").log().diff(self.params.period)).alias("return"),
            ])
            .explode(["datetime", "return"])
            .select(["datetime", "symbol", "return"])
        )

        # 共通バリデーションヘルパーを使用
        return self._validate_output(returns)
```

## 契約事項

### 入力

- `market_data`: `MarketDataSchema` に準拠したDataFrame
- 必須列: `datetime`, `symbol`, `close`

### 出力

- 必須列: `datetime`, `symbol`, `return`
- `return` はFloat64型（NaN許容）
- 出力DataFrameのバリデーションには、`BaseReturnCalculator._validate_output()`ヘルパーメソッドを使用可能（推奨）

### 用途

- シグナル評価時に `SignalSchema` のDataFrameと結合され、順位相関係数が計算される
- バックテストループ内では直接使用されない

### テスタビリティ

- モックMarketDataで簡単にユニットテスト可能
- パラメータ変更が型安全
