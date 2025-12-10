"""TopNPortfolioConstructor - シグナル上位N銘柄でポートフォリオを構築

デフォルト実装として、シグナル値でソートし上位N銘柄を選定する。
contracts/base_portfolio_constructor.md参照。
"""

import polars as pl
from pydantic import Field

from qeel.config.params import PortfolioConstructorParams
from qeel.portfolio_constructors.base import BasePortfolioConstructor


class TopNConstructorParams(PortfolioConstructorParams):
    """上位N銘柄構築のパラメータ

    Attributes:
        top_n: 選定する銘柄数（デフォルト: 10）
        ascending: 昇順ソート（Falseの場合、シグナル大きい順）
    """

    top_n: int = Field(default=10, gt=0, description="選定する銘柄数")
    ascending: bool = Field(default=False, description="昇順ソート（Falseの場合、シグナル大きい順）")


class TopNPortfolioConstructor(BasePortfolioConstructor):
    """シグナル上位N銘柄でポートフォリオを構築するデフォルト実装

    シグナル値でソートし、上位N銘柄を選定する。
    選定された銘柄のシグナル強度（signal列）をメタデータとして含めて返す。

    Note:
        入力のsignals DataFrameには「signal」という名前の列が必須。
        複数シグナルを使用する場合は、事前に合成シグナルを「signal」列として
        追加するか、カスタム実装を使用する。
    """

    params: TopNConstructorParams  # 型の明示化

    def construct(self, signals: pl.DataFrame, current_positions: pl.DataFrame) -> pl.DataFrame:
        """シグナルからポートフォリオを構築する

        Args:
            signals: シグナルDataFrame（SignalSchema準拠、signal列必須）
            current_positions: 現在のポジション（PositionSchema準拠）

        Returns:
            構築済みポートフォリオDataFrame（PortfolioSchema準拠）
            列: datetime, symbol, signal_strength
        """
        # 共通バリデーションヘルパーを使用
        self._validate_inputs(signals, current_positions)

        # 空のシグナルの場合は空のDataFrameを返す
        if signals.height == 0:
            return pl.DataFrame(
                {"datetime": [], "symbol": [], "signal_strength": []},
                schema={
                    "datetime": pl.Datetime,
                    "symbol": pl.String,
                    "signal_strength": pl.Float64,
                },
            )

        # シグナルでソートして上位N銘柄を選定
        portfolio = (
            signals.sort("signal", descending=not self.params.ascending)
            .head(self.params.top_n)
            .select(["datetime", "symbol", "signal"])
            .rename({"signal": "signal_strength"})
        )

        # 共通バリデーションヘルパーを使用
        return self._validate_output(portfolio)
