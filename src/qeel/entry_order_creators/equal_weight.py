"""EqualWeightEntryOrderCreator - 等ウェイトポートフォリオでエントリー注文を生成

デフォルト実装として、選定された銘柄に対して等ウェイト（1/N）で資金を配分し、
open価格で成行注文を生成する。

contracts/base_entry_order_creator.md参照。
"""

import polars as pl
from pydantic import Field

from qeel.config.params import EntryOrderCreatorParams
from qeel.entry_order_creators.base import BaseEntryOrderCreator
from qeel.schemas.validators import OrderSchema


class EqualWeightEntryParams(EntryOrderCreatorParams):
    """等ウェイトポートフォリオのパラメータ

    Attributes:
        capital: 運用資金（デフォルト: 1,000,000）
        rebalance_threshold: リバランス閾値（デフォルト: 0.05）
            現在のポジション比率と目標比率の差が閾値を超えた場合にのみ
            リバランス注文を生成する
    """

    capital: float = Field(default=1_000_000.0, gt=0.0, description="運用資金")
    rebalance_threshold: float = Field(default=0.05, ge=0.0, le=1.0, description="リバランス閾値")


class EqualWeightEntryOrderCreator(BaseEntryOrderCreator):
    """等ウェイトポートフォリオでエントリー注文を生成するデフォルト実装

    選定された銘柄に対して等ウェイト（1/N）で資金を配分し、
    open価格で成行注文を生成する。

    rebalance_thresholdは、現在のポジション比率と目標比率の差が閾値を超えた場合にのみ
    リバランス注文を生成するために使用する。これにより、小さな乖離での不要な取引を抑制する。
    """

    params: EqualWeightEntryParams  # 型の明示化

    def create(
        self,
        portfolio_plan: pl.DataFrame,
        current_positions: pl.DataFrame,
        ohlcv: pl.DataFrame,
    ) -> pl.DataFrame:
        """ポートフォリオ計画とポジションからエントリー注文を生成する

        Args:
            portfolio_plan: 構築済みポートフォリオDataFrame（PortfolioSchema準拠）
            current_positions: 現在のポジション（PositionSchema準拠）
            ohlcv: OHLCV価格データ（OHLCVSchema準拠）

        Returns:
            エントリー注文DataFrame（OrderSchema準拠）
        """
        # 共通バリデーションヘルパーを使用
        self._validate_inputs(portfolio_plan, current_positions, ohlcv)

        if portfolio_plan.height == 0:
            return pl.DataFrame(
                {
                    "symbol": [],
                    "side": [],
                    "quantity": [],
                    "price": [],
                    "order_type": [],
                },
                schema={
                    "symbol": pl.String,
                    "side": pl.String,
                    "quantity": pl.Float64,
                    "price": pl.Float64,
                    "order_type": pl.String,
                },
            )

        n_symbols = portfolio_plan.height
        target_weight = 1.0 / n_symbols  # 目標ウェイト（等ウェイト）

        orders: list[dict[str, str | float | None]] = []
        for row in portfolio_plan.to_dicts():
            symbol = row["symbol"]

            # 現在価格取得（open価格）
            price_row = ohlcv.filter(pl.col("symbol") == symbol)
            if price_row.height == 0:
                continue  # データがない銘柄はスキップ

            current_price = price_row["open"][0]

            # 現在のポジションを取得
            position_row = current_positions.filter(pl.col("symbol") == symbol)
            current_quantity = position_row["quantity"][0] if position_row.height > 0 else 0.0
            current_value = current_quantity * current_price
            current_weight = current_value / self.params.capital if self.params.capital > 0 else 0.0

            # リバランス閾値チェック: 目標比率との差が閾値を超えた場合のみ注文生成
            weight_diff = abs(target_weight - current_weight)
            if weight_diff < self.params.rebalance_threshold:
                continue  # 閾値未満の場合はスキップ

            target_value = self.params.capital * target_weight
            target_quantity = target_value / current_price

            # シグナル強度をportfolio_planから取得（メタデータとして含まれている）
            if "signal_strength" in portfolio_plan.columns:
                signal_value = row["signal_strength"]
            else:
                signal_value = 1.0  # デフォルト値

            # シグナルが正なら買い、負なら売り
            side = "buy" if signal_value > 0 else "sell"

            orders.append(
                {
                    "symbol": symbol,
                    "side": side,
                    "quantity": abs(target_quantity),
                    "price": None,  # 成行
                    "order_type": "market",
                }
            )

        if not orders:
            return pl.DataFrame(
                {
                    "symbol": [],
                    "side": [],
                    "quantity": [],
                    "price": [],
                    "order_type": [],
                },
                schema={
                    "symbol": pl.String,
                    "side": pl.String,
                    "quantity": pl.Float64,
                    "price": pl.Float64,
                    "order_type": pl.String,
                },
            )

        return OrderSchema.validate(pl.DataFrame(orders))
