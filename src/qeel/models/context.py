"""Contextモデル

iterationをまたいで保持されるコンテキストを定義する。
"""

from datetime import datetime

import polars as pl
from pydantic import BaseModel, ConfigDict


class Context(BaseModel):
    """iterationをまたいで保持されるコンテキスト

    current_datetimeはiterationの開始時に設定され、iteration全体を通じて不変。
    signals, portfolio_plan, entry_orders, exit_ordersはiteration内で段階的に構築される。
    current_positionsはBaseExchangeClient.fetch_positions()から動的に取得される。
    Polars DataFrameを直接保持することで、変換コストを排除し、型安全性を確保する。

    Attributes:
        current_datetime: 現在のiteration日時（必須、iteration開始時に設定）
        signals: シグナルDataFrame（SignalSchema準拠、SignalCalculatorの出力）
        portfolio_plan: 構築済みポートフォリオDataFrame（PortfolioSchema準拠、
                        PortfolioConstructorの出力）
        entry_orders: エントリー注文DataFrame（OrderSchema準拠、EntryOrderCreatorの出力）
        exit_orders: エグジット注文DataFrame（OrderSchema準拠、ExitOrderCreatorの出力）
        current_positions: 現在のポジションDataFrame（PositionSchema準拠、
                           BaseExchangeClientから取得）
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    current_datetime: datetime
    signals: pl.DataFrame | None = None
    portfolio_plan: pl.DataFrame | None = None
    entry_orders: pl.DataFrame | None = None
    exit_orders: pl.DataFrame | None = None
    current_positions: pl.DataFrame | None = None
