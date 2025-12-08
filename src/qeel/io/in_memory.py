"""InMemoryIO実装

テスト用のインメモリIO実装を提供する。
"""

import fnmatch
from datetime import datetime

import polars as pl

from qeel.io.base import BaseIO


class InMemoryIO(BaseIO):
    """テスト用インメモリIO実装

    内部dictにデータを保持し、ファイルシステムや外部ストレージに依存しない。
    単体テストやインテグレーションテストで使用することを想定。
    """

    def __init__(self) -> None:
        """インメモリストレージを初期化"""
        self.storage: dict[str, dict[str, object] | pl.DataFrame] = {}

    def get_base_path(self, subdir: str) -> str:
        """メモリ内のベースパスを返す

        Args:
            subdir: サブディレクトリ名

        Returns:
            memory://形式のパス
        """
        return f"memory://{subdir}"

    def get_partition_dir(self, base_path: str, target_datetime: datetime) -> str:
        """年月パーティションパスを返す

        Args:
            base_path: ベースパス
            target_datetime: パーティショニング対象の日時

        Returns:
            パーティションパス（YYYY/MM/形式）
        """
        return f"{base_path}/{target_datetime.strftime('%Y')}/{target_datetime.strftime('%m')}"

    def save(self, path: str, data: dict[str, object] | pl.DataFrame, format: str) -> None:
        """インメモリストレージに保存

        Args:
            path: 保存先パス
            data: 保存するデータ
            format: フォーマット（使用しないが互換性のため保持）
        """
        self.storage[path] = data

    def load(self, path: str, format: str) -> dict[str, object] | pl.DataFrame | None:
        """インメモリストレージから読み込み

        Args:
            path: 読み込み元パス
            format: フォーマット（使用しないが互換性のため保持）

        Returns:
            保存されたデータ。存在しない場合はNone
        """
        return self.storage.get(path)

    def exists(self, path: str) -> bool:
        """データの存在確認

        Args:
            path: 確認対象パス

        Returns:
            データが存在する場合True
        """
        return path in self.storage

    def list_files(self, path: str, pattern: str | None = None) -> list[str]:
        """指定パス配下のデータ一覧を取得

        Args:
            path: 検索対象パス（プレフィックス）
            pattern: ファイル名のフィルタパターン（fnmatch形式）

        Returns:
            マッチしたパスのリスト（ソート済み）
        """
        files = [k for k in self.storage.keys() if k.startswith(path)]

        if pattern:
            files = [f for f in files if fnmatch.fnmatch(f.split("/")[-1], pattern)]

        return sorted(files)
