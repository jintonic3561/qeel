"""ユーザ定義パラメータの基底クラス

各計算クラスのパラメータはこれらの基底クラスを継承して定義する。
data-model.md 3.1-3.5を参照。
"""

from pydantic import BaseModel


class SignalCalculatorParams(BaseModel):
    """シグナル計算クラスのパラメータ基底クラス

    ユーザはこれを継承して独自パラメータを定義する。

    Example:
        class MySignalParams(SignalCalculatorParams):
            window: int = Field(..., gt=0)
            threshold: float = Field(..., ge=0.0, le=1.0)
    """

    pass  # ユーザが拡張


class PortfolioConstructorParams(BaseModel):
    """ポートフォリオ構築クラスのパラメータ基底クラス

    ユーザはこれを継承して独自パラメータを定義する。

    Example:
        class TopNConstructorParams(PortfolioConstructorParams):
            top_n: int = Field(default=10, gt=0, description="選定する銘柄数")
            min_signal_threshold: float = Field(default=0.0, description="最小シグナル閾値")
    """

    pass  # ユーザが拡張


class EntryOrderCreatorParams(BaseModel):
    """エントリー注文生成クラスのパラメータ基底クラス

    ユーザはこれを継承して独自パラメータを定義する。

    Example:
        class EqualWeightParams(EntryOrderCreatorParams):
            capital: float = Field(default=1_000_000.0, gt=0.0, description="運用資金")
            max_position_pct: float = Field(default=0.2, gt=0.0, le=1.0, description="1銘柄の最大ポジション比率")
    """

    pass  # ユーザが拡張


class ExitOrderCreatorParams(BaseModel):
    """エグジット注文生成クラスのパラメータ基底クラス

    ユーザはこれを継承して独自パラメータを定義する。

    Example:
        class FullExitParams(ExitOrderCreatorParams):
            exit_threshold: float = Field(default=1.0, ge=0.0, le=1.0, description="エグジット閾値(保有比率)")
    """

    pass  # ユーザが拡張


class ReturnCalculatorParams(BaseModel):
    """リターン計算クラスのパラメータ基底クラス

    Example:
        class LogReturnParams(ReturnCalculatorParams):
            period: int = Field(default=1, gt=0)
    """

    pass  # ユーザが拡張
