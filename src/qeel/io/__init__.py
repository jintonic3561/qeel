"""IOレイヤーモジュール

ファイル読み書きを抽象化するIOレイヤーを提供する。
Local/S3の判別を一手に引き受け、ContextStoreとDataSourceは
このクラスを経由してデータ操作を行う。
"""

from qeel.io.base import BaseIO
from qeel.io.in_memory import InMemoryIO
from qeel.io.local import LocalIO
from qeel.io.s3 import S3IO

__all__ = ["BaseIO", "LocalIO", "S3IO", "InMemoryIO"]
