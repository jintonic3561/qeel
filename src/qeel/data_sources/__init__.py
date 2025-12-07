"""データソースモジュール

ユーザがデータソース（Parquet、API、データベース等）から
データを取得するための抽象基底クラスとテスト用実装を提供する。
"""

from qeel.data_sources.base import BaseDataSource
from qeel.data_sources.mock import MockDataSource

__all__ = ["BaseDataSource", "MockDataSource"]
