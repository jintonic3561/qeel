"""取引所クライアントモジュール

注文の執行、約定情報の取得、ポジション情報の取得を提供する。
バックテスト時はMockExchangeClient、実運用時はユーザ実装のクライアントを使用する。
"""

from qeel.exchange_clients.base import BaseExchangeClient
from qeel.exchange_clients.mock import MockExchangeClient

__all__ = [
    "BaseExchangeClient",
    "MockExchangeClient",
]
