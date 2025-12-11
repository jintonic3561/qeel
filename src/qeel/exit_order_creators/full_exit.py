"""全ポジション決済注文を生成するデフォルト実装

保有ポジションに対して全決済注文を生成する。
close価格での成行決済。

contracts/base_exit_order_creator.md参照。
"""

import polars as pl
from pydantic import Field

from qeel.config.params import ExitOrderCreatorParams
from qeel.exit_order_creators.base import BaseExitOrderCreator
from qeel.schemas.validators import OrderSchema


class FullExitParams(ExitOrderCreatorParams):
    """全ポジション決済のパラメータ

    Attributes:
        exit_threshold: エグジット閾値（保有比率）。1.0で全決済、0.5で半分決済。
    """

    exit_threshold: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="エグジット閾値（保有比率）",
    )


class FullExitOrderCreator(BaseExitOrderCreator):
    """保有ポジションの全決済注文を生成するデフォルト実装

    保有している全銘柄に対して、close価格で成行決済注文を生成する。
    exit_thresholdで決済比率を調整可能。

    Attributes:
        params: FullExitParams（Pydanticモデル）
    """

    params: FullExitParams

    def __init__(self, params: FullExitParams) -> None:
        """
        Args:
            params: 全ポジション決済パラメータ（Pydanticモデル）
        """
        super().__init__(params)
        self.params = params

    def create(
        self,
        current_positions: pl.DataFrame,
        ohlcv: pl.DataFrame,
    ) -> pl.DataFrame:
        """現在のポジションと価格データから全決済注文を生成する

        Args:
            current_positions: 現在のポジション（PositionSchema準拠）
            ohlcv: OHLCV価格データ（OHLCVSchema準拠、close価格を使用）

        Returns:
            全決済注文DataFrame（OrderSchema準拠）

        Raises:
            ValueError: 入力データが不正またはスキーマ違反の場合
        """
        # 共通バリデーションヘルパーを使用
        self._validate_inputs(current_positions, ohlcv)

        if current_positions.height == 0:
            return pl.DataFrame(
                schema={
                    "symbol": pl.String,
                    "side": pl.String,
                    "quantity": pl.Float64,
                    "price": pl.Float64,
                    "order_type": pl.String,
                }
            )

        orders: list[dict[str, str | float | None]] = []
        for row in current_positions.to_dicts():
            symbol = row["symbol"]
            quantity = row["quantity"]

            if quantity == 0:
                continue  # ポジションがゼロの場合はスキップ

            # exit_thresholdに応じて決済数量を調整
            exit_quantity = abs(quantity) * self.params.exit_threshold

            # 買いポジションは売り、売りポジションは買いで決済
            side = "sell" if quantity > 0 else "buy"

            orders.append(
                {
                    "symbol": symbol,
                    "side": side,
                    "quantity": exit_quantity,
                    "price": None,  # 成行
                    "order_type": "market",
                }
            )

        if not orders:
            return pl.DataFrame(
                schema={
                    "symbol": pl.String,
                    "side": pl.String,
                    "quantity": pl.Float64,
                    "price": pl.Float64,
                    "order_type": pl.String,
                }
            )

        return OrderSchema.validate(pl.DataFrame(orders))
