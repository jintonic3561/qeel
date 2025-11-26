# Contract: BaseSignalCalculator

## 概要

ユーザがシグナル計算ロジックを実装するための抽象基底クラス。Pydanticモデルでパラメータを定義し、`calculate()` メソッドをオーバーライドして、複数のデータソースを入力として受け取り、シグナルを返す。

## インターフェース定義

```python
from abc import ABC, abstractmethod
import polars as pl
from qeel.schemas import SignalCalculatorParams, SignalSchema

class BaseSignalCalculator(ABC):
    """シグナル計算抽象基底クラス

    ユーザはこのクラスを継承し、calculate()メソッドを実装する。

    Attributes:
        params: SignalCalculatorParamsを継承したPydanticモデル
    """

    def __init__(self, params: SignalCalculatorParams):
        """
        Args:
            params: シグナル計算パラメータ（Pydanticモデル）
        """
        self.params = params

    @abstractmethod
    def calculate(self, data_sources: dict[str, pl.DataFrame]) -> pl.DataFrame:
        """シグナルを計算する

        Args:
            data_sources: データソース名をキーとするPolars DataFrameの辞書
                         各DataFrameはMarketDataSchemaに準拠

        Returns:
            シグナルDataFrame（SignalSchemaに準拠）
            必須列: datetime (pl.Datetime), symbol (pl.Utf8), signal (pl.Float64)

        Raises:
            ValueError: データソースが不足している、またはスキーマ不正の場合
        """
        ...
```

## 実装例

```python
from pydantic import BaseModel, Field
import polars as pl
from qeel.calculators import BaseSignalCalculator

class MovingAverageCrossParams(BaseModel):
    short_window: int = Field(..., gt=0, description="短期移動平均のwindow")
    long_window: int = Field(..., gt=0, description="長期移動平均のwindow")

class MovingAverageCrossCalculator(BaseSignalCalculator):
    """移動平均クロス戦略のシグナル計算"""

    def calculate(self, data_sources: dict[str, pl.DataFrame]) -> pl.DataFrame:
        # データソース取得
        if "ohlcv" not in data_sources:
            raise ValueError("ohlcvデータソースが必要です")

        ohlcv = data_sources["ohlcv"]

        # シグナル計算ロジック
        signals = (
            ohlcv
            .sort(["symbol", "datetime"])
            .group_by("symbol")
            .agg([
                pl.col("datetime"),
                pl.col("close")
                  .rolling_mean(window_size=self.params.short_window)
                  .alias("short_ma"),
                pl.col("close")
                  .rolling_mean(window_size=self.params.long_window)
                  .alias("long_ma"),
            ])
            .explode(["datetime", "short_ma", "long_ma"])
            .with_columns([
                (pl.col("short_ma") - pl.col("long_ma")).alias("signal")
            ])
            .select(["datetime", "symbol", "signal"])
        )

        return SignalSchema.validate(signals)
```

## 契約事項

### 入力

- `data_sources`: 辞書形式で複数のデータソースを受け取る
- 各DataFrameは `MarketDataSchema` に準拠していることが保証される
- データは既にiteration範囲でフィルタリングされている

### 出力

- 必ず `SignalSchema` に準拠したDataFrameを返す
- 必須列: `datetime`, `symbol`, `signal`
- `signal` はFloat64型（NaN許容）

### バリデーション

- 出力は `SignalSchema.validate()` でバリデーションすることを推奨
- 不正なスキーマはValueErrorをraiseする

### テスタビリティ

- `data_sources` をモックDataFrameで渡すことでユニットテスト可能
- `params` はPydanticモデルなのでテスト時に型安全に設定変更可能

## 注意事項

- データ欠損（NaN）はユーザが処理する責任を持つ
- シグナル計算ロジックはこのクラス外で事前に検証済みであることを想定
- バックテストと実運用で同一のインスタンスを使用できる
