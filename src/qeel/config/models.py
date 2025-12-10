"""設定モデル

Pydanticを使用した設定のバリデーションとパース。
data-model.md 1.1-1.6を参照。
"""

import re
import tomllib
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
        module: データソースクラスのモジュールパス(例: "qeel.data_sources.parquet")
        class_name: データソースクラス名(例: "ParquetDataSource")
        source_path: データソースのパス(ローカルファイルまたはURI、globパターン対応)
    """

    name: str = Field(..., description="データソース識別子")
    datetime_column: str = Field(..., description="datetime列名")
    offset_seconds: int = Field(default=0, description="利用可能時刻オフセット(秒)")
    window_seconds: int = Field(..., gt=0, description="取得window(秒)")
    module: str = Field(..., description="データソースクラスのモジュールパス")
    class_name: str = Field(..., description="データソースクラス名")
    source_path: str = Field(..., description="ソースパス(globパターン対応)")


class CostConfig(BaseModel):
    """取引コストの設定

    Attributes:
        commission_rate: 手数料率(例: 0.001 = 0.1%)
        slippage_bps: スリッページ(ベーシスポイント)
        market_impact_model: マーケットインパクトモデル("fixed", "linear")
        market_impact_param: マーケットインパクトパラメータ
        market_fill_price_type: 成行注文の約定価格タイプ("next_open", "current_close")
            - "next_open": 翌バーの始値で約定(デフォルト、より現実的)
            - "current_close": 当バーの終値で約定
        limit_fill_bar_type: 指値注文の約定判定バータイプ("next_bar", "current_bar")
            - "next_bar": 翌バーのhigh/lowで約定判定(デフォルト)
            - "current_bar": 当バーのhigh/lowで約定判定
    """

    commission_rate: float = Field(default=0.0, ge=0.0, description="手数料率")
    slippage_bps: float = Field(default=0.0, ge=0.0, description="スリッページ(bps)")
    market_impact_model: str = Field(default="fixed", description="マーケットインパクトモデル")
    market_impact_param: float = Field(default=0.0, ge=0.0, description="マーケットインパクトパラメータ")
    market_fill_price_type: str = Field(default="next_open", description="成行注文の約定価格タイプ")
    limit_fill_bar_type: str = Field(default="next_bar", description="指値注文の約定判定バータイプ")

    @field_validator("market_impact_model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        allowed = {"fixed", "linear"}
        if v not in allowed:
            raise ValueError(f"market_impact_modelは{allowed}のいずれかである必要があります")
        return v

    @field_validator("market_fill_price_type")
    @classmethod
    def validate_fill_price_type(cls, v: str) -> str:
        allowed = {"next_open", "current_close"}
        if v not in allowed:
            raise ValueError(f"market_fill_price_typeは{allowed}のいずれかである必要があります: {v}")
        return v

    @field_validator("limit_fill_bar_type")
    @classmethod
    def validate_limit_fill_bar_type(cls, v: str) -> str:
        allowed = {"next_bar", "current_bar"}
        if v not in allowed:
            raise ValueError(f"limit_fill_bar_typeは{allowed}のいずれかである必要があります: {v}")
        return v


class StepTimingConfig(BaseModel):
    """各ステップの実行タイミング設定

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
        step_timings: 各ステップの実行タイミング
    """

    frequency: timedelta = Field(..., description="iteration頻度")
    start_date: datetime = Field(..., description="開始日")
    end_date: datetime = Field(..., description="終了日")
    universe: list[str] | None = Field(default=None, description="対象銘柄リスト(Noneなら全銘柄)")
    step_timings: StepTimingConfig = Field(default_factory=StepTimingConfig)

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
    """全体設定(戦略名、ストレージタイプとS3設定)

    Attributes:
        strategy_name: 戦略名(S3キープレフィックスに使用、必須)
        storage_type: ストレージタイプ("local"または"s3")
        s3_bucket: S3バケット名(storage_type="s3"の場合必須)
        s3_region: S3リージョン(storage_type="s3"の場合必須)
    """

    strategy_name: str = Field(..., description="戦略名(S3キープレフィックスに使用)")
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


class Config(BaseModel):
    """Qeelの全体設定

    Attributes:
        general: General設定
        data_sources: データソース設定リスト(ohlcvは必須)
        costs: コスト設定
        loop: ループ設定
    """

    general: GeneralConfig
    data_sources: list[DataSourceConfig] = Field(..., min_length=1)
    costs: CostConfig
    loop: LoopConfig

    @model_validator(mode="after")
    def validate_ohlcv_required(self) -> "Config":
        """ohlcvデータソースが必須であることを検証する"""
        names = [ds.name for ds in self.data_sources]
        if "ohlcv" not in names:
            raise ValueError("data_sourcesには'ohlcv'という名前のデータソースが必須です")
        return self

    @classmethod
    def from_toml(cls, path: Path | None = None) -> "Config":
        """tomlファイルから設定を読み込む

        Args:
            path: 設定ファイルのパス。Noneの場合、ワークスペース/configs/config.tomlを使用

        Returns:
            Configインスタンス

        Raises:
            FileNotFoundError: ファイルが存在しない場合
            ValueError: TOMLパースエラーまたはバリデーションエラーの場合
        """
        if path is None:
            from qeel.utils.workspace import get_workspace

            workspace = get_workspace()
            path = workspace / "configs" / "config.toml"

        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls(**data)
