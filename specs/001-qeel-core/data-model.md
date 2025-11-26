# Data Model: Qeel

**Date**: 2025-11-26
**Context**: Phase 1 data model design for Qeel backtest library

## 概要

すべてのデータ構造はPydanticモデルで定義し、実行時バリデーションを保証する。Polars DataFrameを使用するデータは、カスタムバリデータで列スキーマを検証する。

---

## 1. Configuration Models

### 1.1 DataSourceConfig

```python
from pydantic import BaseModel, Field, field_validator
from pathlib import Path

class DataSourceConfig(BaseModel):
    """データソースの設定

    Attributes:
        name: データソース名（例: "ohlcv", "earnings"）
        datetime_column: datetime列の列名
        offset_hours: データ利用可能時刻のオフセット（時間）
        window_days: 取得するデータのwindow（日数）
        source_type: ソースタイプ（"csv", "parquet", "custom"）
        source_path: データソースのパス（ローカルファイルまたはURI）
    """
    name: str = Field(..., description="データソース識別子")
    datetime_column: str = Field(..., description="datetime列名")
    offset_hours: int = Field(default=0, description="利用可能時刻オフセット（時間）")
    window_days: int = Field(..., gt=0, description="取得window（日数）")
    source_type: str = Field(..., description="ソースタイプ")
    source_path: Path = Field(..., description="ソースパス")

    @field_validator('source_type')
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        allowed = {"csv", "parquet", "custom"}
        if v not in allowed:
            raise ValueError(f"source_typeは{allowed}のいずれかである必要があります: {v}")
        return v
```

### 1.2 CostConfig

```python
class CostConfig(BaseModel):
    """取引コストの設定

    Attributes:
        commission_rate: 手数料率（例: 0.001 = 0.1%）
        slippage_bps: スリッページ（ベーシスポイント）
        market_impact_model: マーケットインパクトモデル（"fixed", "linear"）
        market_impact_param: マーケットインパクトパラメータ
    """
    commission_rate: float = Field(default=0.0, ge=0.0, description="手数料率")
    slippage_bps: float = Field(default=0.0, ge=0.0, description="スリッページ（bps）")
    market_impact_model: str = Field(default="fixed", description="マーケットインパクトモデル")
    market_impact_param: float = Field(default=0.0, ge=0.0, description="マーケットインパクトパラメータ")

    @field_validator('market_impact_model')
    @classmethod
    def validate_model(cls, v: str) -> str:
        allowed = {"fixed", "linear"}
        if v not in allowed:
            raise ValueError(f"market_impact_modelは{allowed}のいずれかである必要があります")
        return v
```

### 1.3 LoopConfig

```python
from datetime import timedelta

class MethodTimingConfig(BaseModel):
    """各メソッドの実行タイミング設定

    Attributes:
        calculate_signals_offset: シグナル計算のオフセット
        select_symbols_offset: 銘柄選定のオフセット
        create_orders_offset: 注文生成のオフセット
        submit_orders_offset: 注文執行のオフセット
    """
    calculate_signals_offset: timedelta = Field(default=timedelta(hours=0))
    select_symbols_offset: timedelta = Field(default=timedelta(hours=0))
    create_orders_offset: timedelta = Field(default=timedelta(hours=0))
    submit_orders_offset: timedelta = Field(default=timedelta(hours=0))


class LoopConfig(BaseModel):
    """バックテストループの設定

    Attributes:
        frequency: iteration頻度（"1d", "1w", "1h"等）
        start_date: 開始日
        end_date: 終了日
        method_timings: 各メソッドの実行タイミング
    """
    frequency: str = Field(..., description="iteration頻度")
    start_date: datetime = Field(..., description="開始日")
    end_date: datetime = Field(..., description="終了日")
    method_timings: MethodTimingConfig = Field(default_factory=MethodTimingConfig)

    @field_validator('end_date')
    @classmethod
    def end_after_start(cls, v: datetime, info) -> datetime:
        if 'start_date' in info.data and v <= info.data['start_date']:
            raise ValueError("end_dateはstart_dateより後である必要があります")
        return v
```

### 1.4 Config（全体設定）

```python
class Config(BaseModel):
    """Qeelの全体設定

    Attributes:
        data_sources: データソース設定リスト
        costs: コスト設定
        loop: ループ設定
    """
    data_sources: list[DataSourceConfig] = Field(..., min_length=1)
    costs: CostConfig
    loop: LoopConfig

    @classmethod
    def from_toml(cls, path: Path) -> "Config":
        """tomlファイルから設定を読み込む"""
        import tomli
        with open(path, "rb") as f:
            data = tomli.load(f)
        return cls(**data)
```

---

## 2. Domain Models

### 2.1 MarketData

```python
import polars as pl

class MarketDataSchema:
    """MarketDataのPolarsスキーマ定義

    必須列:
        datetime: pl.Datetime - データ利用可能時刻
        symbol: pl.Utf8 - 銘柄コード
        close: pl.Float64 - 終値

    オプション列（データソース依存）:
        open: pl.Float64
        high: pl.Float64
        low: pl.Float64
        volume: pl.Int64
    """
    REQUIRED_COLUMNS = {
        "datetime": pl.Datetime,
        "symbol": pl.Utf8,
        "close": pl.Float64,
    }

    @staticmethod
    def validate(df: pl.DataFrame) -> pl.DataFrame:
        """スキーマバリデーション"""
        for col, dtype in MarketDataSchema.REQUIRED_COLUMNS.items():
            if col not in df.columns:
                raise ValueError(f"必須列が不足しています: {col}")
            if df[col].dtype != dtype:
                raise ValueError(f"列'{col}'の型が不正です。期待: {dtype}, 実際: {df[col].dtype}")
        return df
```

### 2.2 Signal

```python
class SignalSchema:
    """Signalの Polarsスキーマ定義

    必須列:
        datetime: pl.Datetime - シグナル生成日時
        symbol: pl.Utf8 - 銘柄コード
        signal: pl.Float64 - シグナル値
    """
    REQUIRED_COLUMNS = {
        "datetime": pl.Datetime,
        "symbol": pl.Utf8,
        "signal": pl.Float64,
    }

    @staticmethod
    def validate(df: pl.DataFrame) -> pl.DataFrame:
        for col, dtype in SignalSchema.REQUIRED_COLUMNS.items():
            if col not in df.columns:
                raise ValueError(f"必須列が不足しています: {col}")
            if df[col].dtype != dtype:
                raise ValueError(f"列'{col}'の型が不正です。期待: {dtype}, 実際: {df[col].dtype}")
        return df
```

### 2.3 Position

```python
class PositionSchema:
    """Positionの Polarsスキーマ定義

    必須列:
        symbol: pl.Utf8 - 銘柄コード
        quantity: pl.Float64 - 保有数量
        avg_price: pl.Float64 - 平均取得単価
    """
    REQUIRED_COLUMNS = {
        "symbol": pl.Utf8,
        "quantity": pl.Float64,
        "avg_price": pl.Float64,
    }

    @staticmethod
    def validate(df: pl.DataFrame) -> pl.DataFrame:
        for col, dtype in PositionSchema.REQUIRED_COLUMNS.items():
            if col not in df.columns:
                raise ValueError(f"必須列が不足しています: {col}")
            if df[col].dtype != dtype:
                raise ValueError(f"列'{col}'の型が不正です。期待: {dtype}, 実際: {df[col].dtype}")
        return df
```

### 2.4 Order

```python
class OrderSchema:
    """Orderの Polarsスキーマ定義

    必須列:
        symbol: pl.Utf8 - 銘柄コード
        side: pl.Utf8 - 売買区分（"buy" / "sell"）
        quantity: pl.Float64 - 数量
        price: pl.Float64 - 価格（nullの場合は成行）
        order_type: pl.Utf8 - 注文タイプ（"market", "limit"）
    """
    REQUIRED_COLUMNS = {
        "symbol": pl.Utf8,
        "side": pl.Utf8,
        "quantity": pl.Float64,
        "price": pl.Float64,  # nullable for market orders
        "order_type": pl.Utf8,
    }

    @staticmethod
    def validate(df: pl.DataFrame) -> pl.DataFrame:
        for col, dtype in OrderSchema.REQUIRED_COLUMNS.items():
            if col not in df.columns:
                raise ValueError(f"必須列が不足しています: {col}")
            # price以外はnull不可
            if col != "price" and df[col].null_count() > 0:
                raise ValueError(f"列'{col}'にnullが含まれています")

        # sideのバリデーション
        allowed_sides = {"buy", "sell"}
        actual_sides = set(df["side"].unique().to_list())
        if not actual_sides.issubset(allowed_sides):
            raise ValueError(f"不正なside値: {actual_sides - allowed_sides}")

        # order_typeのバリデーション
        allowed_types = {"market", "limit"}
        actual_types = set(df["order_type"].unique().to_list())
        if not actual_types.issubset(allowed_types):
            raise ValueError(f"不正なorder_type値: {actual_types - allowed_types}")

        return df
```

### 2.5 FillReport

```python
class FillReportSchema:
    """FillReportの Polarsスキーマ定義

    必須列:
        order_id: pl.Utf8 - 注文ID
        symbol: pl.Utf8 - 銘柄コード
        side: pl.Utf8 - 売買区分
        filled_quantity: pl.Float64 - 約定数量
        filled_price: pl.Float64 - 約定価格
        commission: pl.Float64 - 手数料
        timestamp: pl.Datetime - 約定タイムスタンプ
    """
    REQUIRED_COLUMNS = {
        "order_id": pl.Utf8,
        "symbol": pl.Utf8,
        "side": pl.Utf8,
        "filled_quantity": pl.Float64,
        "filled_price": pl.Float64,
        "commission": pl.Float64,
        "timestamp": pl.Datetime,
    }

    @staticmethod
    def validate(df: pl.DataFrame) -> pl.DataFrame:
        for col, dtype in FillReportSchema.REQUIRED_COLUMNS.items():
            if col not in df.columns:
                raise ValueError(f"必須列が不足しています: {col}")
            if df[col].dtype != dtype:
                raise ValueError(f"列'{col}'の型が不正です。期待: {dtype}, 実際: {df[col].dtype}")
        return df
```

### 2.6 Context

```python
from typing import Any

class Context(BaseModel):
    """iterationをまたいで保持されるコンテキスト

    Attributes:
        current_date: 現在のiteration日時
        positions: 現在のポジション（Polars DataFrame, PositionSchema）
        selected_symbols: 選定された銘柄リスト
        model_params: ユーザ定義のモデルパラメータ（任意）
    """
    current_date: datetime
    positions: dict[str, Any]  # positions DataFrameをdictに変換して保存
    selected_symbols: list[str]
    model_params: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_dataframe(cls, current_date: datetime, positions_df: pl.DataFrame, selected_symbols: list[str], model_params: dict[str, Any]) -> "Context":
        """Polars DataFrameからContextを生成"""
        return cls(
            current_date=current_date,
            positions=positions_df.to_dict(as_series=False),
            selected_symbols=selected_symbols,
            model_params=model_params,
        )

    def get_positions_df(self) -> pl.DataFrame:
        """PositionsをPolars DataFrameとして取得"""
        if not self.positions:
            return pl.DataFrame(schema=PositionSchema.REQUIRED_COLUMNS)
        return pl.DataFrame(self.positions)
```

### 2.7 Metrics

```python
class MetricsSchema:
    """Metricsの Polarsスキーマ定義

    必須列:
        date: pl.Date - 日付
        daily_return: pl.Float64 - 日次リターン
        cumulative_return: pl.Float64 - 累積リターン
        volatility: pl.Float64 - ボラティリティ
        sharpe_ratio: pl.Float64 - シャープレシオ
        max_drawdown: pl.Float64 - 最大ドローダウン
    """
    REQUIRED_COLUMNS = {
        "date": pl.Date,
        "daily_return": pl.Float64,
        "cumulative_return": pl.Float64,
        "volatility": pl.Float64,
        "sharpe_ratio": pl.Float64,
        "max_drawdown": pl.Float64,
    }

    @staticmethod
    def validate(df: pl.DataFrame) -> pl.DataFrame:
        for col, dtype in MetricsSchema.REQUIRED_COLUMNS.items():
            if col not in df.columns:
                raise ValueError(f"必須列が不足しています: {col}")
            if df[col].dtype != dtype:
                raise ValueError(f"列'{col}'の型が不正です。期待: {dtype}, 実際: {df[col].dtype}")
        return df
```

---

## 3. Parameter Models（ユーザ定義）

### 3.1 SignalCalculatorParams

```python
class SignalCalculatorParams(BaseModel):
    """シグナル計算クラスのパラメータ基底クラス

    ユーザはこれを継承して独自パラメータを定義する。

    Example:
        class MySignalParams(SignalCalculatorParams):
            window: int = Field(..., gt=0)
            threshold: float = Field(..., ge=0.0, le=1.0)
    """
    pass  # ユーザが拡張
```

### 3.2 ReturnCalculatorParams

```python
class ReturnCalculatorParams(BaseModel):
    """リターン計算クラスのパラメータ基底クラス

    Example:
        class LogReturnParams(ReturnCalculatorParams):
            period: int = Field(default=1, gt=0)
    """
    pass  # ユーザが拡張
```

---

## 4. Entity Relationships

```
Config
 ├─ DataSourceConfig[]
 ├─ CostConfig
 └─ LoopConfig

Context
 ├─ current_date: datetime
 ├─ positions: DataFrame (PositionSchema)
 ├─ selected_symbols: list[str]
 └─ model_params: dict

BacktestEngine
 ├─ config: Config
 ├─ calculator: BaseSignalCalculator (params: SignalCalculatorParams)
 ├─ data_sources: dict[str, BaseDataSource]
 └─ context_store: BaseContextStore

Iteration Flow:
  MarketData (DataSource)
    → Signal (SignalCalculator)
    → Selected Symbols (select_symbols)
    → Order (create_orders)
    → FillReport (Executor)
    → Metrics (calculate_metrics)
```

---

## 5. Validation Strategy

すべてのPolars DataFrameを受け取る関数は、冒頭でスキーマバリデーションを実行する：

```python
def process_signals(signals: pl.DataFrame) -> pl.DataFrame:
    SignalSchema.validate(signals)
    # 処理ロジック
    ...
```

Pydanticモデルは、インスタンス化時に自動バリデーションされる：

```python
config = Config.from_toml(Path("config.toml"))  # 不正な設定はValidationError
```

エラーメッセージは日本語で、不足項目・型不一致・制約違反を明示する。
