"""エントリー注文生成の抽象基底クラス

ユーザがポートフォリオ計画（選定銘柄+メタデータ）とポジションから
エントリー注文を生成するロジックを実装するための抽象基底クラス。

contracts/base_entry_order_creator.md参照。
"""

from abc import ABC, abstractmethod

import polars as pl

from qeel.config.params import EntryOrderCreatorParams
from qeel.schemas.validators import OHLCVSchema, PortfolioSchema, PositionSchema


class BaseEntryOrderCreator(ABC):
    """エントリー注文生成抽象基底クラス

    ユーザはこのクラスを継承し、create()メソッドを実装する。

    Attributes:
        params: EntryOrderCreatorParams（Pydanticモデル）
    """

    def __init__(self, params: EntryOrderCreatorParams) -> None:
        """
        Args:
            params: エントリー注文生成パラメータ（Pydanticモデル）
        """
        self.params = params

    def _validate_inputs(
        self,
        portfolio_plan: pl.DataFrame,
        current_positions: pl.DataFrame,
        ohlcv: pl.DataFrame,
    ) -> None:
        """入力データの共通バリデーション

        サブクラスで任意に呼び出し可能なヘルパーメソッド。
        スキーマバリデーションを一箇所で実行し、重複を避ける。

        Args:
            portfolio_plan: 構築済みポートフォリオDataFrame（PortfolioSchema準拠）
            current_positions: 現在のポジション（PositionSchema準拠）
            ohlcv: OHLCV価格データ（OHLCVSchema準拠）

        Raises:
            ValueError: スキーマ違反の場合
        """
        PortfolioSchema.validate(portfolio_plan)
        PositionSchema.validate(current_positions)
        OHLCVSchema.validate(ohlcv)

    @abstractmethod
    def create(
        self,
        portfolio_plan: pl.DataFrame,
        current_positions: pl.DataFrame,
        ohlcv: pl.DataFrame,
    ) -> pl.DataFrame:
        """ポートフォリオ計画とポジションからエントリー注文を生成する

        Args:
            portfolio_plan: 構築済みポートフォリオDataFrame（PortfolioSchema準拠、メタデータ含む）
                必須列: datetime, symbol
                オプション列: signal_strength, priority, tags等（PortfolioConstructorから渡される）
            current_positions: 現在のポジション（PositionSchema準拠）
            ohlcv: OHLCV価格データ（OHLCVSchema準拠、価格情報取得用）

        Returns:
            エントリー注文DataFrame（OrderSchema準拠）

        Raises:
            ValueError: 入力データが不正またはスキーマ違反の場合
        """
        ...
