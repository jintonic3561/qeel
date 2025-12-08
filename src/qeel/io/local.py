"""LocalIO実装

ローカルファイルシステムへのIO操作を提供する。
"""

import fnmatch
import json
from datetime import datetime
from pathlib import Path

import polars as pl

from qeel.io.base import BaseIO
from qeel.utils import get_workspace


class LocalIO(BaseIO):
    """ローカルファイルシステムIO実装

    ワークスペースディレクトリ配下でファイル読み書きを行う。
    """

    def get_base_path(self, subdir: str) -> str:
        """ワークスペース配下のサブディレクトリパスを返す

        Args:
            subdir: サブディレクトリ名（例: "outputs"）

        Returns:
            ワークスペース配下のパス文字列
        """
        workspace = get_workspace()
        return str(workspace / subdir)

    def get_partition_dir(self, base_path: str, target_datetime: datetime) -> str:
        """年月パーティションディレクトリを返す（YYYY/MM/）

        ディレクトリが存在しない場合は自動作成する。

        Args:
            base_path: ベースパス
            target_datetime: パーティショニング対象の日時

        Returns:
            パーティションディレクトリパス
        """
        partition_dir = Path(base_path) / target_datetime.strftime("%Y") / target_datetime.strftime("%m")
        partition_dir.mkdir(parents=True, exist_ok=True)
        return str(partition_dir)

    def save(self, path: str, data: dict[str, object] | pl.DataFrame, format: str) -> None:
        """ローカルファイルに保存

        Args:
            path: 保存先パス
            data: 保存するデータ
            format: フォーマット（"json"または"parquet"）

        Raises:
            ValueError: サポートされていないフォーマット、
                       またはデータ型が不正な場合
        """
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        elif format == "parquet":
            if not isinstance(data, pl.DataFrame):
                raise ValueError("parquet形式の保存にはpl.DataFrameが必要です")
            data.write_parquet(file_path)
        else:
            raise ValueError(f"サポートされていないフォーマット: {format}")

    def load(self, path: str, format: str) -> dict[str, object] | pl.DataFrame | None:
        """ローカルファイルから読み込み

        Args:
            path: 読み込み元パス
            format: フォーマット（"json"または"parquet"）

        Returns:
            読み込んだデータ。存在しない場合はNone

        Raises:
            ValueError: サポートされていないフォーマット
        """
        file_path = Path(path)
        if not file_path.exists():
            return None

        if format == "json":
            with open(file_path, encoding="utf-8") as f:
                return json.load(f)  # type: ignore[no-any-return]
        elif format == "parquet":
            return pl.read_parquet(file_path)
        else:
            raise ValueError(f"サポートされていないフォーマット: {format}")

    def exists(self, path: str) -> bool:
        """ファイルの存在確認

        Args:
            path: 確認対象パス

        Returns:
            ファイルが存在する場合True
        """
        return Path(path).exists()

    def list_files(self, path: str, pattern: str | None = None) -> list[str]:
        """指定パス配下のファイル一覧を取得

        Args:
            path: 検索対象ディレクトリパス
            pattern: ファイル名のフィルタパターン（fnmatch形式）

        Returns:
            マッチしたファイルパスのリスト（フルパス、ソート済み）
        """
        dir_path = Path(path)
        if not dir_path.exists():
            return []

        files = [str(f) for f in dir_path.rglob("*") if f.is_file()]

        if pattern:
            files = [f for f in files if fnmatch.fnmatch(Path(f).name, pattern)]

        return sorted(files)
