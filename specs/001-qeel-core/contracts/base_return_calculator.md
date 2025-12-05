# Contract: BaseReturnCalculator

## 概要

ユーザがリターン計算ロジックを実装するための抽象基底クラス。シグナル評価時に使用され、市場データを入力として受け取り、**current_datetimeで生成されたシグナルに対する未来の実現リターン系列**を返す。リーク（ルックアヘッドバイアス）を防ぐため、リターンは必ず前向き（forward）に計算しなければならない。

## インターフェース定義

```python
from abc import ABC, abstractmethod

import polars as pl

from qeel.schemas import ReturnCalculatorParams, ReturnSchema


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

        return ReturnSchema.validate(returns)

    @abstractmethod
    def calculate(self, ohlcv: pl.DataFrame) -> pl.DataFrame:
        """リターンを計算する

        Args:
            ohlcv: OHLCVSchemaに準拠したPolars DataFrame

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
import polars as pl
from pydantic import BaseModel, Field

from qeel.calculators.returns.base import BaseReturnCalculator


class LogReturnParams(BaseModel):
    period: int = Field(default=1, gt=0, description="リターン計算期間（日数）")

class LogReturnCalculator(BaseReturnCalculator):
    """対数リターン計算（前向き/forward return）

    current_datetimeで生成されたシグナルに対する未来の実現リターンを計算する。
    リーク防止のため、period日後の価格を使用して前向きリターンを算出。
    """

    def calculate(self, ohlcv: pl.DataFrame) -> pl.DataFrame:
        returns = (
            ohlcv
            .sort(["symbol", "datetime"])
            .group_by("symbol")
            .agg([
                pl.col("datetime"),
                # 未来の実現リターンを計算（forward return）
                # shift(-period)でperiod日後の価格を取得し、現在価格との差分を計算
                (pl.col("close").log().shift(-self.params.period) - pl.col("close").log()).alias("return"),
            ])
            .explode(["datetime", "return"])
            .select(["datetime", "symbol", "return"])
        )

        # 共通バリデーションヘルパーを使用
        return self._validate_output(returns)
```

## 契約事項

### 入力

- `ohlcv`: `OHLCVSchema` に準拠したDataFrame

### 出力

- 必須列: `datetime`, `symbol`, `return`
- `return` はFloat64型（NaN許容）
- 出力DataFrameのバリデーションには、`BaseReturnCalculator._validate_output()`ヘルパーメソッドを使用可能（推奨）

### リーク防止（重要）

- **リターンは必ず前向き（forward）に計算する**: リターンは`current_datetime`で生成されたシグナルに対する**未来の実現リターン**を表す
- **過去リターンの使用は厳禁**: `diff(period)`のような過去差分は、ルックアヘッドバイアス（未来情報の漏洩）を引き起こすため使用してはならない
- **時系列の整合性**: シグナル生成時点（datetime）における未来リターンを計算することで、バックテストの再現性を保証する

### 用途

- **シグナル評価**: シグナル評価時に`SignalSchema`のDataFrameと`datetime`, `symbol`で結合され、順位相関係数が計算される
  - シグナル（datetime, symbol, signal）とリターン（datetime, symbol, return）を結合
  - 各datetime（シグナル生成時点）における、シグナルと未来の実現リターンの順位相関を評価
- **バックテストループとの分離**: バックテストループ内では直接使用されない（ループ内では約定履歴によってパフォーマンスが計算される）

### テスタビリティ

- モックOHLCVデータで簡単にユニットテスト可能
- パラメータ変更が型安全
