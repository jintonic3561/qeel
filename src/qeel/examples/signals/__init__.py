"""シグナル計算の実装例

移動平均クロス戦略などの実装例を提供する。
"""

from qeel.examples.signals.moving_average import (
    MovingAverageCrossCalculator,
    MovingAverageCrossParams,
)

__all__ = ["MovingAverageCrossCalculator", "MovingAverageCrossParams"]
