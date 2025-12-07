# Data Model: Qeel

**Date**: 2025-11-26
**Context**: Phase 1 data model design for Qeel backtest library

## 概要

すべてのデータ構造はPydanticモデルで定義し、実行時バリデーションを保証する。Polars DataFrameを使用するデータは、カスタムバリデータで列スキーマを検証する。

---

## 1. Configuration Models

### 1.1 DataSourceConfig

```python
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


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
import re
from datetime import datetime, timedelta

from pydantic import BaseModel, Field, field_validator


class StepTimingConfig(BaseModel):
    """各ステップの実行タイミング設定

    Attributes:
        calculate_signals_offset_seconds: シグナル計算のオフセット（秒）
        construct_portfolio_offset_seconds: ポートフォリオ構築のオフセット（秒）
        create_entry_orders_offset_seconds: エントリー注文生成のオフセット（秒）
        create_exit_orders_offset_seconds: エグジット注文生成のオフセット（秒）
        submit_entry_orders_offset_seconds: エントリー注文執行のオフセット（秒）
        submit_exit_orders_offset_seconds: エグジット注文執行のオフセット（秒）
    """
    calculate_signals_offset_seconds: int = Field(default=0, description="シグナル計算のオフセット（秒）")
    construct_portfolio_offset_seconds: int = Field(default=0, description="ポートフォリオ構築のオフセット（秒）")
    create_entry_orders_offset_seconds: int = Field(default=0, description="エントリー注文生成のオフセット（秒）")
    create_exit_orders_offset_seconds: int = Field(default=0, description="エグジット注文生成のオフセット（秒）")
    submit_entry_orders_offset_seconds: int = Field(default=0, description="エントリー注文執行のオフセット（秒）")
    submit_exit_orders_offset_seconds: int = Field(default=0, description="エグジット注文執行のオフセット（秒）")


class LoopConfig(BaseModel):
    """バックテストループの設定

    Attributes:
        frequency: iteration頻度（timedeltaとして保持、tomlでは"1d", "1h"等の文字列で指定）
        start_date: 開始日
        end_date: 終了日
        universe: 対象銘柄リスト（Noneなら全銘柄を対象）
        step_timings: 各ステップの実行タイミング
    """
    frequency: timedelta = Field(..., description="iteration頻度")
    start_date: datetime = Field(..., description="開始日")
    end_date: datetime = Field(..., description="終了日")
    universe: list[str] | None = Field(default=None, description="対象銘柄リスト（Noneなら全銘柄）")
    step_timings: StepTimingConfig = Field(default_factory=StepTimingConfig)

    @field_validator('frequency', mode='before')
    @classmethod
    def parse_frequency(cls, v: str | timedelta) -> timedelta:
        """文字列形式のfrequency（"1d", "4h", "1w", "30m"）をtimedeltaに変換する

        Args:
            v: frequency値（文字列またはtimedelta）

        Returns:
            timedelta形式のfrequency

        Raises:
            ValueError: 不正な形式の場合
        """
        if isinstance(v, timedelta):
            return v

        match = re.match(r'^(\d+)([dhwm])$', v.lower())
        if not match:
            raise ValueError(
                f"不正なfrequency形式です: {v}（有効な形式: '1d', '4h', '1w', '30m'）"
            )

        value, unit = int(match.group(1)), match.group(2)
        unit_map = {'d': 'days', 'h': 'hours', 'w': 'weeks', 'm': 'minutes'}
        return timedelta(**{unit_map[unit]: value})

    @field_validator('end_date')
    @classmethod
    def end_after_start(cls, v: datetime, info) -> datetime:
        if 'start_date' in info.data and v <= info.data['start_date']:
            raise ValueError("end_dateはstart_dateより後である必要があります")
        return v
```

### 1.4 GeneralConfig

```python
from pydantic import BaseModel, Field, field_validator


class GeneralConfig(BaseModel):
    """全体設定（ストレージタイプとS3設定）

    Attributes:
        storage_type: ストレージタイプ（"local"または"s3"）
        s3_bucket: S3バケット名（storage_type="s3"の場合必須）
        s3_region: S3リージョン（storage_type="s3"の場合必須）
    """
    storage_type: str = Field(..., description="ストレージタイプ")
    s3_bucket: str | None = Field(default=None, description="S3バケット名")
    s3_region: str | None = Field(default=None, description="S3リージョン")

    @field_validator('storage_type')
    @classmethod
    def validate_storage_type(cls, v: str) -> str:
        allowed = {"local", "s3"}
        if v not in allowed:
            raise ValueError(f"storage_typeは{allowed}のいずれかである必要があります: {v}")
        return v

    @field_validator('s3_bucket')
    @classmethod
    def validate_s3_bucket(cls, v: str | None, info) -> str | None:
        if info.data.get('storage_type') == 's3' and v is None:
            raise ValueError("storage_type='s3'の場合、s3_bucketは必須です")
        return v

    @field_validator('s3_region')
    @classmethod
    def validate_s3_region(cls, v: str | None, info) -> str | None:
        if info.data.get('storage_type') == 's3' and v is None:
            raise ValueError("storage_type='s3'の場合、s3_regionは必須です")
        return v
```

### 1.5 Workspace Utilities

```python
import os
from pathlib import Path


def get_workspace() -> Path:
    """ワークスペースディレクトリを取得する

    環境変数QEEL_WORKSPACEが設定されている場合はそのパスを返し、
    未設定の場合はカレントディレクトリを返す。

    Returns:
        ワークスペースディレクトリのPathオブジェクト

    Raises:
        ValueError: 指定されたパスが存在しないディレクトリの場合

    Example:
        # 環境変数で指定
        $ export QEEL_WORKSPACE=/path/to/my_backtest
        >>> get_workspace()
        PosixPath('/path/to/my_backtest')

        # 環境変数未設定（カレントディレクトリを使用）
        >>> get_workspace()
        PosixPath('/current/working/directory')
    """
    workspace_env = os.environ.get("QEEL_WORKSPACE")

    if workspace_env is not None:
        workspace = Path(workspace_env)
        if not workspace.is_dir():
            raise ValueError(
                f"QEEL_WORKSPACEで指定されたパスが存在しないか、ディレクトリではありません: {workspace}"
            )
        return workspace

    return Path.cwd()
```

### 1.6 Config（全体設定）

```python
import tomllib
from pathlib import Path

from pydantic import BaseModel, Field

from qeel.utils.workspace import get_workspace


class Config(BaseModel):
    """Qeelの全体設定

    Attributes:
        general: General設定
        data_sources: データソース設定リスト
        costs: コスト設定
        loop: ループ設定
    """
    general: GeneralConfig
    data_sources: list[DataSourceConfig] = Field(..., min_length=1)
    costs: CostConfig
    loop: LoopConfig

    @classmethod
    def from_toml(cls, path: Path | None = None) -> "Config":
        """tomlファイルから設定を読み込む

        Args:
            path: 設定ファイルのパス。Noneの場合、ワークスペース/configs/config.tomlを使用
        """
        if path is None:
            workspace = get_workspace()
            path = workspace / "configs" / "config.toml"

        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls(**data)
```

---

## 2. Domain Models

### 2.1 OHLCV

```python
import polars as pl

class OHLCVSchema:
    """OHLCVのPolarsスキーマ定義

    必須列:
        datetime: pl.Datetime - データ利用可能時刻
        symbol: pl.Utf8 - 銘柄コード
        open: pl.Float64
        high: pl.Float64
        low: pl.Float64
        close: pl.Float64
        volume: pl.Int64

    Note:
        BaseDataSourceは任意のスキーマを返すことができ、OHLCVSchemaは
        OHLCV価格データに特化したデータソースの参照例として提供される。
    """
    REQUIRED_COLUMNS = {
        "datetime": pl.Datetime,
        "symbol": pl.Utf8,
        "open": pl.Float64,
        "high": pl.Float64,
        "low": pl.Float64,
        "close": pl.Float64,
        "volume": pl.Int64,
    }

    @staticmethod
    def validate(df: pl.DataFrame) -> pl.DataFrame:
        """スキーマバリデーション（必須列のみ）"""
        for col, dtype in OHLCVSchema.REQUIRED_COLUMNS.items():
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
from datetime import datetime

import polars as pl
from pydantic import BaseModel, ConfigDict


class Context(BaseModel):
    """iterationをまたいで保持されるコンテキスト

    current_datetimeはiterationの開始時に設定され、iteration全体を通じて不変。
    signals, portfolio_plan, entry_orders, exit_ordersはiteration内で段階的に構築される。
    current_positionsはBaseExchangeClient.fetch_positions()から動的に取得される。
    Polars DataFrameを直接保持することで、変換コストを排除し、型安全性を確保する。

    Attributes:
        current_datetime: 現在のiteration日時（必須、iteration開始時に設定）
        signals: シグナルDataFrame（SignalSchema準拠、SignalCalculatorの出力）
        portfolio_plan: 構築済みポートフォリオDataFrame（PortfolioSchema準拠、PortfolioConstructorの出力）
        entry_orders: エントリー注文DataFrame（OrderSchema準拠、EntryOrderCreatorの出力）
        exit_orders: エグジット注文DataFrame（OrderSchema準拠、ExitOrderCreatorの出力）
        current_positions: 現在のポジションDataFrame（PositionSchema準拠、BaseExchangeClientから取得）
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    current_datetime: datetime
    signals: pl.DataFrame | None = None
    portfolio_plan: pl.DataFrame | None = None
    entry_orders: pl.DataFrame | None = None
    exit_orders: pl.DataFrame | None = None
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

### 2.9 IO Models

```python
from abc import ABC, abstractmethod
from datetime import datetime
from io import BytesIO
from pathlib import Path

import boto3
import polars as pl

from qeel.config import GeneralConfig
from qeel.utils import get_workspace


class BaseIO(ABC):
    """ファイル読み書きを抽象化するIOレイヤー

    Local/S3の判別を一手に引き受け、ContextStoreとDataSourceはこのクラスを経由してデータ操作を行う。
    """

    @classmethod
    def from_config(cls, general_config: GeneralConfig) -> "BaseIO":
        """General設定から適切なIO実装を返すファクトリメソッド

        Args:
            general_config: General設定

        Returns:
            storage_typeに応じたIO実装（LocalIOまたはS3IO）
        """
        if general_config.storage_type == "local":
            return LocalIO()
        elif general_config.storage_type == "s3":
            if general_config.s3_bucket is None or general_config.s3_region is None:
                raise ValueError("storage_type='s3'の場合、s3_bucketとs3_regionは必須です")
            return S3IO(bucket=general_config.s3_bucket, region=general_config.s3_region)
        else:
            raise ValueError(f"サポートされていないストレージタイプ: {general_config.storage_type}")

    @abstractmethod
    def get_base_path(self, subdir: str) -> str:
        """ベースパスを取得する

        Args:
            subdir: サブディレクトリ（"inputs"、"outputs"等）

        Returns:
            ベースパス文字列（ローカルパスまたはS3キープレフィックス）
        """
        ...

    @abstractmethod
    def get_partition_dir(self, base_path: str, target_datetime: datetime) -> str:
        """年月パーティショニングディレクトリを取得する

        Args:
            base_path: ベースパス
            target_datetime: パーティショニング対象の日時

        Returns:
            パーティションディレクトリパス（YYYY/MM/形式）
        """
        ...

    @abstractmethod
    def save(self, path: str, data: dict | pl.DataFrame, format: str) -> None:
        """データを保存する

        Args:
            path: 保存先パス（ベースパスからの相対パス）
            data: 保存するデータ（dictまたはDataFrame）
            format: フォーマット（"json"または"parquet"）
        """
        ...

    @abstractmethod
    def load(self, path: str, format: str) -> dict | pl.DataFrame | None:
        """データを読み込む

        Args:
            path: 読み込み元パス（ベースパスからの相対パス）
            format: フォーマット（"json"または"parquet"）

        Returns:
            読み込んだデータ。存在しない場合はNone
        """
        ...

    @abstractmethod
    def exists(self, path: str) -> bool:
        """ファイルが存在するか確認する

        Args:
            path: 確認対象パス

        Returns:
            ファイルが存在する場合True
        """
        ...


class LocalIO(BaseIO):
    """ローカルファイルシステムIO実装"""

    def get_base_path(self, subdir: str) -> str:
        """ワークスペース配下のサブディレクトリパスを返す"""
        workspace = get_workspace()
        return str(workspace / subdir)

    def get_partition_dir(self, base_path: str, target_datetime: datetime) -> str:
        """年月パーティションディレクトリを返す（YYYY/MM/）"""
        partition_dir = Path(base_path) / target_datetime.strftime("%Y") / target_datetime.strftime("%m")
        partition_dir.mkdir(parents=True, exist_ok=True)
        return str(partition_dir)

    def save(self, path: str, data: dict | pl.DataFrame, format: str) -> None:
        """ローカルファイルに保存"""
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            import json
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        elif format == "parquet":
            if not isinstance(data, pl.DataFrame):
                raise ValueError("parquet形式の保存にはpl.DataFrameが必要です")
            data.write_parquet(file_path)
        else:
            raise ValueError(f"サポートされていないフォーマット: {format}")

    def load(self, path: str, format: str) -> dict | pl.DataFrame | None:
        """ローカルファイルから読み込み"""
        file_path = Path(path)
        if not file_path.exists():
            return None

        if format == "json":
            import json
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        elif format == "parquet":
            return pl.read_parquet(file_path)
        else:
            raise ValueError(f"サポートされていないフォーマット: {format}")

    def exists(self, path: str) -> bool:
        """ファイルの存在確認"""
        return Path(path).exists()


class S3IO(BaseIO):
    """S3ストレージIO実装"""

    def __init__(self, bucket: str, region: str):
        self.bucket = bucket
        self.region = region
        self.s3_client = boto3.client('s3', region_name=region)

    def get_base_path(self, subdir: str) -> str:
        """S3キープレフィックスを返す（qeel/{subdir}/）"""
        return f"qeel/{subdir}"

    def get_partition_dir(self, base_path: str, target_datetime: datetime) -> str:
        """年月パーティションキープレフィックスを返す（YYYY/MM/）"""
        return f"{base_path}/{target_datetime.strftime('%Y')}/{target_datetime.strftime('%m')}"

    def save(self, path: str, data: dict | pl.DataFrame, format: str) -> None:
        """S3に保存"""
        if format == "json":
            import json
            body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        elif format == "parquet":
            if not isinstance(data, pl.DataFrame):
                raise ValueError("parquet形式の保存にはpl.DataFrameが必要です")
            buffer = BytesIO()
            data.write_parquet(buffer)
            buffer.seek(0)
            body = buffer.getvalue()
        else:
            raise ValueError(f"サポートされていないフォーマット: {format}")

        self.s3_client.put_object(Bucket=self.bucket, Key=path, Body=body)

    def load(self, path: str, format: str) -> dict | pl.DataFrame | None:
        """S3から読み込み"""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=path)
            body = response['Body'].read()

            if format == "json":
                import json
                return json.loads(body.decode('utf-8'))
            elif format == "parquet":
                buffer = BytesIO(body)
                return pl.read_parquet(buffer)
            else:
                raise ValueError(f"サポートされていないフォーマット: {format}")
        except self.s3_client.exceptions.NoSuchKey:
            return None

    def exists(self, path: str) -> bool:
        """S3オブジェクトの存在確認"""
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=path)
            return True
        except self.s3_client.exceptions.ClientError:
            return False
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

### 3.3 EntryOrderCreatorParams

```python
class EntryOrderCreatorParams(BaseModel):
    """エントリー注文生成クラスのパラメータ基底クラス

    ユーザはこれを継承して独自パラメータを定義する。

    Example:
        class EqualWeightParams(EntryOrderCreatorParams):
            capital: float = Field(default=1_000_000.0, gt=0.0, description="運用資金")
            max_position_pct: float = Field(default=0.2, gt=0.0, le=1.0, description="1銘柄の最大ポジション比率")
    """
    pass  # ユーザが拡張
```

### 3.4 ExitOrderCreatorParams

```python
class ExitOrderCreatorParams(BaseModel):
    """エグジット注文生成クラスのパラメータ基底クラス

    ユーザはこれを継承して独自パラメータを定義する。

    Example:
        class FullExitParams(ExitOrderCreatorParams):
            exit_threshold: float = Field(default=1.0, ge=0.0, le=1.0, description="エグジット閾値（保有比率）")
    """
    pass  # ユーザが拡張
```

### 3.5 ReturnCalculatorParams

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
 ├─ entry_orders: DataFrame (OrderSchema) | None
 ├─ exit_orders: DataFrame (OrderSchema) | None
 └─ current_positions: DataFrame (PositionSchema) | None

StrategyEngine
 ├─ config: Config
 ├─ calculator: BaseSignalCalculator (params: SignalCalculatorParams)
 ├─ portfolio_constructor: BasePortfolioConstructor (params: PortfolioConstructorParams)
 ├─ entry_order_creator: BaseEntryOrderCreator (params: EntryOrderCreatorParams)
 ├─ exit_order_creator: BaseExitOrderCreator (params: ExitOrderCreatorParams)
 ├─ data_sources: dict[str, BaseDataSource]
 └─ context_store: BaseContextStore

BacktestRunner
 ├─ engine: StrategyEngine
 └─ config: Config

Iteration Flow:
  OHLCV / その他データソース (DataSource)
    → Signal (SignalCalculator)
    → Portfolio DataFrame (PortfolioConstructor: 銘柄選定+メタデータ付与)
    → Entry Order (EntryOrderCreator: メタデータ活用)
    → Exit Order (ExitOrderCreator: ポジションベース)
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
