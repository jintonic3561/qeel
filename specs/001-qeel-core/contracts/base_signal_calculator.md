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
            必須列: datetime (pl.Datetime), symbol (pl.Utf8)
            オプション列: signal (pl.Float64) または任意のシグナル列（例: signal_momentum, signal_value等）

        Raises:
            ValueError: データソースが不足している、またはスキーマ不正の場合
        """
        ...
```

## 実装例

```python
from pydantic import BaseModel, Field
import polars as pl
from qeel.calculators.signals.base import BaseSignalCalculator

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

### 複数シグナルの実装例

```python
class MultiSignalParams(BaseModel):
    momentum_window: int = Field(default=20, gt=0)
    value_threshold: float = Field(default=0.5, gt=0.0)

class MultiSignalCalculator(BaseSignalCalculator):
    """複数のシグナルを同時に計算する例"""

    def calculate(self, data_sources: dict[str, pl.DataFrame]) -> pl.DataFrame:
        if "ohlcv" not in data_sources:
            raise ValueError("ohlcvデータソースが必要です")

        ohlcv = data_sources["ohlcv"]

        # 複数のシグナルを計算
        signals = (
            ohlcv
            .sort(["symbol", "datetime"])
            .group_by("symbol")
            .agg([
                pl.col("datetime"),
                # モメンタムシグナル
                (pl.col("close").pct_change(self.params.momentum_window))
                  .alias("signal_momentum"),
                # バリューシグナル（例: PER的な指標）
                (pl.col("close") / pl.col("volume").rolling_mean(window_size=20))
                  .alias("signal_value"),
            ])
            .explode(["datetime", "signal_momentum", "signal_value"])
            .select(["datetime", "symbol", "signal_momentum", "signal_value"])
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
- 必須列: `datetime`, `symbol`
- オプション列: `signal` または任意のシグナル列（例: `signal_momentum`, `signal_value`等、Float64型、NaN許容）

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
