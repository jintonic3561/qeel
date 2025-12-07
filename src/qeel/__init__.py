"""Qeel - 量的トレーディング向けバックテストライブラリ

バックテストから実運用へのシームレスな接続を可能とするPythonバックテストライブラリ。
"""

from qeel.config.models import Config
from qeel.utils.workspace import get_workspace

__version__ = "0.1.0"

__all__ = [
    "Config",
    "get_workspace",
]
