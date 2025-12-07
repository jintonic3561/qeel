"""Parameter Modelsのユニットテスト

TDD: RED → GREEN → REFACTOR
data-model.md 3.1-3.5を参照
"""

from pydantic import Field


def test_signal_calculator_params_extensible() -> None:
    """継承してカスタムパラメータ追加可能"""
    from qeel.config.params import SignalCalculatorParams

    class MySignalParams(SignalCalculatorParams):
        window: int = Field(..., gt=0)
        threshold: float = Field(..., ge=0.0, le=1.0)

    params = MySignalParams(window=10, threshold=0.5)
    assert params.window == 10
    assert params.threshold == 0.5


def test_portfolio_constructor_params_extensible() -> None:
    """継承してカスタムパラメータ追加可能"""
    from qeel.config.params import PortfolioConstructorParams

    class TopNConstructorParams(PortfolioConstructorParams):
        top_n: int = Field(default=10, gt=0, description="選定する銘柄数")
        min_signal_threshold: float = Field(default=0.0, description="最小シグナル閾値")

    params = TopNConstructorParams(top_n=5, min_signal_threshold=0.3)
    assert params.top_n == 5
    assert params.min_signal_threshold == 0.3


def test_entry_order_creator_params_extensible() -> None:
    """継承してカスタムパラメータ追加可能"""
    from qeel.config.params import EntryOrderCreatorParams

    class EqualWeightParams(EntryOrderCreatorParams):
        capital: float = Field(default=1_000_000.0, gt=0.0, description="運用資金")
        max_position_pct: float = Field(default=0.2, gt=0.0, le=1.0, description="1銘柄の最大ポジション比率")

    params = EqualWeightParams(capital=500_000.0, max_position_pct=0.1)
    assert params.capital == 500_000.0
    assert params.max_position_pct == 0.1


def test_exit_order_creator_params_extensible() -> None:
    """継承してカスタムパラメータ追加可能"""
    from qeel.config.params import ExitOrderCreatorParams

    class FullExitParams(ExitOrderCreatorParams):
        exit_threshold: float = Field(default=1.0, ge=0.0, le=1.0, description="エグジット閾値(保有比率)")

    params = FullExitParams(exit_threshold=0.8)
    assert params.exit_threshold == 0.8


def test_return_calculator_params_extensible() -> None:
    """継承してカスタムパラメータ追加可能"""
    from qeel.config.params import ReturnCalculatorParams

    class LogReturnParams(ReturnCalculatorParams):
        period: int = Field(default=1, gt=0)

    params = LogReturnParams(period=5)
    assert params.period == 5
