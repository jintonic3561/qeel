"""BaseIO ABC

ファイル読み書きを抽象化するIOレイヤーの基底クラスを定義する。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from qeel.config import GeneralConfig


class BaseIO(ABC):
    """ファイル読み書きを抽象化するIOレイヤー

    Local/S3の判別を一手に引き受け、ContextStoreとDataSourceは
    このクラスを経由してデータ操作を行う。
    """

    @classmethod
    def from_config(cls, general_config: GeneralConfig) -> BaseIO:
        """General設定から適切なIO実装を返すファクトリメソッド

        Args:
            general_config: General設定

        Returns:
            storage_typeに応じたIO実装（LocalIOまたはS3IO）

        Raises:
            ValueError: storage_typeがサポートされていない場合、
                       またはs3設定が不足している場合
        """
        # 循環importを避けるためここでimport
        from qeel.io.local import LocalIO
        from qeel.io.s3 import S3IO

        if general_config.storage_type == "local":
            return LocalIO()
        elif general_config.storage_type == "s3":
            if general_config.s3_bucket is None or general_config.s3_region is None:
                raise ValueError("storage_type='s3'の場合、s3_bucketとs3_regionは必須です")
            return S3IO(
                strategy_name=general_config.strategy_name,
                bucket=general_config.s3_bucket,
                region=general_config.s3_region,
            )
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
    def save(self, path: str, data: dict[str, object] | pl.DataFrame, format: str) -> None:
        """データを保存する

        Args:
            path: 保存先パス（ベースパスからの相対パスまたは絶対パス）
            data: 保存するデータ（dictまたはDataFrame）
            format: フォーマット（"json"または"parquet"）

        Raises:
            ValueError: サポートされていないフォーマット、
                       またはデータ型が不正な場合
            RuntimeError: 保存失敗時
        """
        ...

    @abstractmethod
    def load(self, path: str, format: str) -> dict[str, object] | pl.DataFrame | None:
        """データを読み込む

        Args:
            path: 読み込み元パス（ベースパスからの相対パスまたは絶対パス）
            format: フォーマット（"json"または"parquet"）

        Returns:
            読み込んだデータ。存在しない場合はNone

        Raises:
            ValueError: サポートされていないフォーマット
            RuntimeError: 読み込み失敗時（破損など、ファイル不在以外）
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

    @abstractmethod
    def list_files(self, path: str, pattern: str | None = None) -> list[str]:
        """指定パス配下のファイル一覧を取得する

        Args:
            path: 検索対象ディレクトリパス（LocalIOの場合はローカルパス、
                  S3IOの場合はキープレフィックス）
            pattern: ファイル名のフィルタパターン（例: "signals_*.parquet"）。
                    Noneの場合は全ファイル

        Returns:
            マッチしたファイルパスのリスト（フルパス）。存在しない場合は空リスト
        """
        ...
