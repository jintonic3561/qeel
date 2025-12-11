"""エグジット注文生成の抽象基底クラス

ユーザが現在のポジションと価格データからエグジット注文を生成する
ロジックを実装するための抽象基底クラス。

contracts/base_exit_order_creator.md参照。
"""

from abc import ABC, abstractmethod

import polars as pl

from qeel.config.params import ExitOrderCreatorParams
from qeel.schemas.validators import OHLCVSchema, PositionSchema


class BaseExitOrderCreator(ABC):
    """エグジット注文生成抽象基底クラス

    ユーザはこのクラスを継承し、create()メソッドを実装する。

    Attributes:
        params: ExitOrderCreatorParams（Pydanticモデル）
    """

    def __init__(self, params: ExitOrderCreatorParams) -> None:
        """
        Args:
            params: エグジット注文生成パラメータ（Pydanticモデル）
        """
        self.params = params

    def _validate_inputs(
        self,
        current_positions: pl.DataFrame,
        ohlcv: pl.DataFrame,
    ) -> None:
        """入力データの共通バリデーション

        サブクラスで任意に呼び出し可能なヘルパーメソッド。
        スキーマバリデーションを一箇所で実行し、重複を避ける。

        Args:
            current_positions: 現在のポジション（PositionSchema準拠）
            ohlcv: OHLCV価格データ（OHLCVSchema準拠）

        Raises:
            ValueError: スキーマ違反の場合
        """
        PositionSchema.validate(current_positions)
        OHLCVSchema.validate(ohlcv)

    @abstractmethod
    def create(
        self,
        current_positions: pl.DataFrame,
        ohlcv: pl.DataFrame,
    ) -> pl.DataFrame:
        """現在のポジションと価格データからエグジット注文を生成する

        Args:
            current_positions: 現在のポジション（PositionSchema準拠）
            ohlcv: OHLCV価格データ（OHLCVSchema準拠、価格情報取得用）

        Returns:
            エグジット注文DataFrame（OrderSchema準拠）

        Raises:
            ValueError: 入力データが不正またはスキーマ違反の場合
        """
        ...
