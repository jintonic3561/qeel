"""設定モデル

Pydanticを使用した設定のバリデーションとパース。
data-model.md 1.1-1.6を参照。
"""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class DataSourceConfig(BaseModel):
    """データソースの設定

    Attributes:
        name: データソース名(例: "ohlcv", "earnings")
        datetime_column: datetime列の列名
        offset_seconds: データ利用可能時刻のオフセット(秒)
            - 取得windowを調整することでオフセットを適用
            - 例: offset_seconds=3600の場合、window(start, end)は(start-1h, end-1h)に調整される
        window_seconds: 取得するデータのwindow(秒)
        source_type: ソースタイプ("parquet", "custom")
        source_path: データソースのパス(ローカルファイルまたはURI)
    """

    name: str = Field(..., description="データソース識別子")
    datetime_column: str = Field(..., description="datetime列名")
    offset_seconds: int = Field(default=0, description="利用可能時刻オフセット(秒)")
    window_seconds: int = Field(..., gt=0, description="取得window(秒)")
    source_type: str = Field(..., description="ソースタイプ")
    source_path: Path = Field(..., description="ソースパス")

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        allowed = {"parquet", "custom"}
        if v not in allowed:
            raise ValueError(f"source_typeは{allowed}のいずれかである必要があります: {v}")
        return v


class CostConfig(BaseModel):
    """取引コストの設定

    Attributes:
        commission_rate: 手数料率(例: 0.001 = 0.1%)
        slippage_bps: スリッページ(ベーシスポイント)
        market_impact_model: マーケットインパクトモデル("fixed", "linear")
        market_impact_param: マーケットインパクトパラメータ
    """

    commission_rate: float = Field(default=0.0, ge=0.0, description="手数料率")
    slippage_bps: float = Field(default=0.0, ge=0.0, description="スリッページ(bps)")
    market_impact_model: str = Field(default="fixed", description="マーケットインパクトモデル")
    market_impact_param: float = Field(default=0.0, ge=0.0, description="マーケットインパクトパラメータ")

    @field_validator("market_impact_model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        allowed = {"fixed", "linear"}
        if v not in allowed:
            raise ValueError(f"market_impact_modelは{allowed}のいずれかである必要があります")
        return v


class MethodTimingConfig(BaseModel):
    """各メソッドの実行タイミング設定

    Attributes:
        calculate_signals_offset_seconds: シグナル計算のオフセット(秒)
        construct_portfolio_offset_seconds: ポートフォリオ構築のオフセット(秒)
        create_entry_orders_offset_seconds: エントリー注文生成のオフセット(秒)
        create_exit_orders_offset_seconds: エグジット注文生成のオフセット(秒)
        submit_entry_orders_offset_seconds: エントリー注文執行のオフセット(秒)
        submit_exit_orders_offset_seconds: エグジット注文執行のオフセット(秒)
    """

    calculate_signals_offset_seconds: int = Field(default=0, description="シグナル計算のオフセット(秒)")
    construct_portfolio_offset_seconds: int = Field(default=0, description="ポートフォリオ構築のオフセット(秒)")
    create_entry_orders_offset_seconds: int = Field(default=0, description="エントリー注文生成のオフセット(秒)")
    create_exit_orders_offset_seconds: int = Field(default=0, description="エグジット注文生成のオフセット(秒)")
    submit_entry_orders_offset_seconds: int = Field(default=0, description="エントリー注文執行のオフセット(秒)")
    submit_exit_orders_offset_seconds: int = Field(default=0, description="エグジット注文執行のオフセット(秒)")


class LoopConfig(BaseModel):
    """バックテストループの設定

    Attributes:
        frequency: iteration頻度(timedeltaとして保持、tomlでは"1d", "1h"等の文字列で指定)
        start_date: 開始日
        end_date: 終了日
        universe: 対象銘柄リスト(Noneなら全銘柄を対象)
        method_timings: 各メソッドの実行タイミング
    """

    frequency: timedelta = Field(..., description="iteration頻度")
    start_date: datetime = Field(..., description="開始日")
    end_date: datetime = Field(..., description="終了日")
    universe: list[str] | None = Field(default=None, description="対象銘柄リスト(Noneなら全銘柄)")
    method_timings: MethodTimingConfig = Field(default_factory=MethodTimingConfig)

    @field_validator("frequency", mode="before")
    @classmethod
    def parse_frequency(cls, v: str | timedelta) -> timedelta:
        """文字列形式のfrequency("1d", "4h", "1w", "30m")をtimedeltaに変換する

        Args:
            v: frequency値(文字列またはtimedelta)

        Returns:
            timedelta形式のfrequency

        Raises:
            ValueError: 不正な形式の場合
        """
        if isinstance(v, timedelta):
            return v

        match = re.match(r"^(\d+)([dhwm])$", v.lower())
        if not match:
            raise ValueError(f"不正なfrequency形式です: {v}(有効な形式: '1d', '4h', '1w', '30m')")

        value, unit = int(match.group(1)), match.group(2)
        unit_map = {"d": "days", "h": "hours", "w": "weeks", "m": "minutes"}
        return timedelta(**{unit_map[unit]: value})

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: datetime, info: Any) -> datetime:
        if "start_date" in info.data and v <= info.data["start_date"]:
            raise ValueError("end_dateはstart_dateより後である必要があります")
        return v


class GeneralConfig(BaseModel):
    """全体設定(ストレージタイプとS3設定)

    Attributes:
        storage_type: ストレージタイプ("local"または"s3")
        s3_bucket: S3バケット名(storage_type="s3"の場合必須)
        s3_region: S3リージョン(storage_type="s3"の場合必須)
    """

    storage_type: str = Field(..., description="ストレージタイプ")
    s3_bucket: str | None = Field(default=None, description="S3バケット名")
    s3_region: str | None = Field(default=None, description="S3リージョン")

    @field_validator("storage_type")
    @classmethod
    def validate_storage_type(cls, v: str) -> str:
        allowed = {"local", "s3"}
        if v not in allowed:
            raise ValueError(f"storage_typeは{allowed}のいずれかである必要があります: {v}")
        return v

    @model_validator(mode="after")
    def validate_s3_config(self) -> "GeneralConfig":
        """S3設定の検証(storage_type='s3'の場合、s3_bucketとs3_regionが必須)"""
        if self.storage_type == "s3":
            if self.s3_bucket is None:
                raise ValueError("storage_type='s3'の場合、s3_bucketは必須です")
            if self.s3_region is None:
                raise ValueError("storage_type='s3'の場合、s3_regionは必須です")
        return self
