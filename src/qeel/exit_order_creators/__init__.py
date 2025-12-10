"""エグジット注文生成モジュール

ユーザが現在のポジションからエグジット注文を生成するロジックを
実装するための抽象基底クラスとデフォルト実装を提供する。
"""

from qeel.exit_order_creators.base import BaseExitOrderCreator

__all__ = [
    "BaseExitOrderCreator",
]
