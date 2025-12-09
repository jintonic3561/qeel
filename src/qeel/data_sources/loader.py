"""データソースローダー

設定から全データソースを一括生成するユーティリティ関数を提供する。
ohlcvデータソースにはOHLCVSchemaバリデーションを自動適用する。
"""

from __future__ import annotations

import importlib
from datetime import datetime
from typing import TYPE_CHECKING

import polars as pl

from qeel.data_sources.base import BaseDataSource
from qeel.schemas import OHLCVSchema

if TYPE_CHECKING:
    from qeel.config import Config
    from qeel.io.base import BaseIO


class OHLCVValidatingDataSource(BaseDataSource):
    """OHLCVスキーマバリデーション付きデータソースラッパー

    fetch()の戻り値に対してOHLCVSchema.validate()を自動適用する。
    """

    def __init__(self, inner: BaseDataSource) -> None:
        """
        Args:
            inner: ラップ対象のデータソース
        """
        # 親クラスの__init__は呼ばず、innerのconfigとioを参照
        self._inner = inner
        self.config = inner.config
        self.io = inner.io

    def fetch(self, start: datetime, end: datetime, symbols: list[str]) -> pl.DataFrame:
        """データを取得し、OHLCVSchemaでバリデーションする

        Args:
            start: 開始日時
            end: 終了日時
            symbols: 銘柄コードリスト

        Returns:
            OHLCVSchema準拠のPolars DataFrame

        Raises:
            ValueError: OHLCVSchemaバリデーション失敗時
        """
        df = self._inner.fetch(start, end, symbols)
        return OHLCVSchema.validate(df)


def _import_class(module_path: str, class_name: str) -> type[BaseDataSource]:
    """モジュールパスとクラス名からクラスを動的インポートする

    Args:
        module_path: モジュールパス(例: "qeel.data_sources.parquet")
        class_name: クラス名(例: "ParquetDataSource")

    Returns:
        インポートしたクラス

    Raises:
        ImportError: モジュールが見つからない場合
        AttributeError: クラスが見つからない場合
    """
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls  # type: ignore[no-any-return]


def load_data_sources(config: Config, io: BaseIO) -> dict[str, BaseDataSource]:
    """設定から全データソースを一括生成する

    各DataSourceConfigに対して:
    1. module/class_nameからクラスを動的インポート
    2. クラスをインスタンス化(configとioを渡す)
    3. name="ohlcv"の場合はOHLCVバリデーション付きラッパーで包む

    Args:
        config: Qeel設定
        io: IOレイヤー実装

    Returns:
        データソース名をキーとするdict

    Raises:
        ImportError: データソースクラスのインポートに失敗した場合
        ValueError: データソースのインスタンス化に失敗した場合

    Example:
        >>> config = Config.from_toml()
        >>> io = BaseIO.from_config(config.general)
        >>> data_sources = load_data_sources(config, io)
        >>> ohlcv_data = data_sources["ohlcv"].fetch(start, end, symbols)
    """
    data_sources: dict[str, BaseDataSource] = {}

    for ds_config in config.data_sources:
        # クラスを動的インポート
        cls = _import_class(ds_config.module, ds_config.class_name)

        # インスタンス化
        instance = cls(ds_config, io)

        # ohlcvの場合はバリデーション付きラッパーで包む
        if ds_config.name == "ohlcv":
            instance = OHLCVValidatingDataSource(instance)

        data_sources[ds_config.name] = instance

    return data_sources
