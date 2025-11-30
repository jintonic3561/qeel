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
        offset_seconds: データ利用可能時刻のオフセット（秒）
            - 取得windowを調整することでオフセットを適用
            - 例: offset_seconds=3600の場合、window(start, end)は(start-1h, end-1h)に調整される
        window_seconds: 取得するデータのwindow（秒）
        source_type: ソースタイプ（"parquet", "custom"）
        source_path: データソースのパス（ローカルファイルまたはURI）
    """
    name: str = Field(..., description="データソース識別子")
    datetime_column: str = Field(..., description="datetime列名")
    offset_seconds: int = Field(default=0, description="利用可能時刻オフセット（秒）")
    window_seconds: int = Field(..., gt=0, description="取得window（秒）")
    source_type: str = Field(..., description="ソースタイプ")
    source_path: Path = Field(..., description="ソースパス")

    @field_validator('source_type')
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        allowed = {"parquet", "custom"}
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
        universe: 対象銘柄リスト（Noneなら全銘柄を対象）
        method_timings: 各メソッドの実行タイミング
    """
    frequency: str = Field(..., description="iteration頻度")
    start_date: datetime = Field(..., description="開始日")
    end_date: datetime = Field(..., description="終了日")
    universe: list[str] | None = Field(default=None, description="対象銘柄リスト（Noneなら全銘柄）")
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

    オプション列（データソース依存）:
        open: pl.Float64
        high: pl.Float64
        low: pl.Float64
        close: pl.Float64
        volume: pl.Int64

    Note:
        BaseDataSourceは任意のスキーマを返すことができ、MarketDataSchemaは
        市場データに特化したデータソースの参照例として提供される。
        システムは強制的なバリデーションを行わない。
    """
    REQUIRED_COLUMNS = {
        "datetime": pl.Datetime,
        "symbol": pl.Utf8,
    }

    @staticmethod
    def validate(df: pl.DataFrame) -> pl.DataFrame:
        """スキーマバリデーション（必須列のみ）"""
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

    オプション列例（ユーザが任意に追加可能）:
        signal: pl.Float64 - シグナル値（単一シグナルの場合）
        signal_momentum: pl.Float64 - モメンタムシグナル（複数シグナルの例）
        signal_value: pl.Float64 - バリューシグナル（複数シグナルの例）
        その他、ユーザが定義する任意のシグナル列
    """
    REQUIRED_COLUMNS = {
        "datetime": pl.Datetime,
        "symbol": pl.Utf8,
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

### 2.3 Portfolio (構築済みポートフォリオ)

```python
class PortfolioSchema:
    """Portfolioの Polarsスキーマ定義

    必須列:
        datetime: pl.Datetime - 構築日時
        symbol: pl.Utf8 - 銘柄コード

    オプション列（ユーザが任意に追加可能）:
        signal_strength: pl.Float64 - シグナル強度
        priority: pl.Int64 - 優先度
        tags: pl.Utf8 - タグ（カスタムメタデータ）
    """
    REQUIRED_COLUMNS = {
        "datetime": pl.Datetime,
        "symbol": pl.Utf8,
    }

    @staticmethod
    def validate(df: pl.DataFrame) -> pl.DataFrame:
        """必須列のみを検証し、オプション列は自由"""
        for col, dtype in PortfolioSchema.REQUIRED_COLUMNS.items():
            if col not in df.columns:
                raise ValueError(f"必須列が不足しています: {col}")
            if df[col].dtype != dtype:
                raise ValueError(f"列'{col}'の型が不正です。期待: {dtype}, 実際: {df[col].dtype}")
        return df
```

### 2.4 Position

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

### 2.5 Order

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

### 2.6 FillReport

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

### 2.7 Context

```python
from typing import Any
from pydantic import ConfigDict

class Context(BaseModel):
    """iterationをまたいで保持されるコンテキスト

    current_datetimeはiterationの開始時に設定され、iteration全体を通じて不変。
    signals, portfolio_plan, ordersはiteration内で段階的に構築される。
    current_positionsはBaseExchangeClient.fetch_positions()から動的に取得される。
    Polars DataFrameを直接保持することで、変換コストを排除し、型安全性を確保する。

    Attributes:
        current_datetime: 現在のiteration日時（必須、iteration開始時に設定）
        signals: シグナルDataFrame（SignalSchema準拠、SignalCalculatorの出力）
        portfolio_plan: 構築済みポートフォリオDataFrame（PortfolioSchema準拠、PortfolioConstructorの出力）
        orders: 注文DataFrame（OrderSchema準拠、OrderCreatorの出力）
        current_positions: 現在のポジションDataFrame（PositionSchema準拠、BaseExchangeClientから取得）
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    current_datetime: datetime
    signals: pl.DataFrame | None = None
    portfolio_plan: pl.DataFrame | None = None
    orders: pl.DataFrame | None = None
    current_positions: pl.DataFrame | None = None
```

### 2.8 Metrics

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

### 3.2 PortfolioConstructorParams

```python
class PortfolioConstructorParams(BaseModel):
    """ポートフォリオ構築クラスのパラメータ基底クラス

    ユーザはこれを継承して独自パラメータを定義する。

    Example:
        class TopNConstructorParams(PortfolioConstructorParams):
            top_n: int = Field(default=10, gt=0, description="選定する銘柄数")
            min_signal_threshold: float = Field(default=0.0, description="最小シグナル閾値")
    """
    pass  # ユーザが拡張
```

### 3.3 OrderCreatorParams

```python
class OrderCreatorParams(BaseModel):
    """注文生成クラスのパラメータ基底クラス

    ユーザはこれを継承して独自パラメータを定義する。

    Example:
        class EqualWeightParams(OrderCreatorParams):
            capital: float = Field(default=1_000_000.0, gt=0.0, description="運用資金")
            max_position_pct: float = Field(default=0.2, gt=0.0, le=1.0, description="1銘柄の最大ポジション比率")
    """
    pass  # ユーザが拡張
```

### 3.4 ReturnCalculatorParams

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
 ├─ current_datetime: datetime
 ├─ signals: DataFrame (SignalSchema) | None
 ├─ portfolio_plan: DataFrame (PortfolioSchema) | None
 ├─ orders: DataFrame (OrderSchema) | None
 └─ current_positions: DataFrame (PositionSchema) | None

BacktestEngine
 ├─ config: Config
 ├─ calculator: BaseSignalCalculator (params: SignalCalculatorParams)
 ├─ portfolio_constructor: BasePortfolioConstructor (params: PortfolioConstructorParams)
 ├─ order_creator: BaseOrderCreator (params: OrderCreatorParams)
 ├─ data_sources: dict[str, BaseDataSource]
 └─ context_store: BaseContextStore

Iteration Flow:
  MarketData (DataSource)
    → Signal (SignalCalculator)
    → Portfolio DataFrame (PortfolioConstructor: 銘柄選定+メタデータ付与)
    → Order (OrderCreator: メタデータ活用)
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
