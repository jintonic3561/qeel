"""ポートフォリオ構築の抽象基底クラス

ユーザがシグナルからポートフォリオを構築するロジックを実装するための
抽象基底クラス。銘柄選定と執行条件の前処理（メタデータ付与）を同時に行い、
OrderCreatorに渡す。

contracts/base_portfolio_constructor.md参照。
"""

from abc import ABC, abstractmethod

import polars as pl

from qeel.config.params import PortfolioConstructorParams
from qeel.schemas.validators import PortfolioSchema, PositionSchema, SignalSchema


class BasePortfolioConstructor(ABC):
    """ポートフォリオ構築抽象基底クラス

    ユーザはこのクラスを継承し、construct()メソッドを実装する。

    Attributes:
        params: PortfolioConstructorParams（Pydanticモデル）
    """

    def __init__(self, params: PortfolioConstructorParams) -> None:
        """
        Args:
            params: ポートフォリオ構築パラメータ（Pydanticモデル）
        """
        self.params = params

    def _validate_inputs(
        self, signals: pl.DataFrame, current_positions: pl.DataFrame
    ) -> None:
        """入力データの共通バリデーション

        サブクラスで任意に呼び出し可能なヘルパーメソッド。
        スキーマバリデーションを一箇所で実行し、重複を避ける。

        Args:
            signals: シグナルDataFrame（SignalSchema準拠）
            current_positions: 現在のポジション（PositionSchema準拠）

        Raises:
            ValueError: スキーマ違反の場合
        """
        SignalSchema.validate(signals)
        PositionSchema.validate(current_positions)

    def _validate_output(self, portfolio: pl.DataFrame) -> pl.DataFrame:
        """出力ポートフォリオの共通バリデーション

        サブクラスで任意に呼び出し可能なヘルパーメソッド。
        スキーマバリデーションを一箇所で実行し、重複を避ける。

        Args:
            portfolio: 構築済みポートフォリオDataFrame（PortfolioSchema準拠）

        Returns:
            バリデーション済みのDataFrame

        Raises:
            ValueError: スキーマ違反の場合
        """
        return PortfolioSchema.validate(portfolio)

    @abstractmethod
    def construct(
        self, signals: pl.DataFrame, current_positions: pl.DataFrame
    ) -> pl.DataFrame:
        """シグナルからポートフォリオを構築し、執行条件計算に必要なメタデータを含むDataFrameを返す

        Args:
            signals: シグナルDataFrame（SignalSchema準拠）
            current_positions: 現在のポジション（PositionSchema準拠）

        Returns:
            構築済みポートフォリオDataFrame（PortfolioSchema準拠）
            必須列: datetime, symbol
            オプション列: signal_strength, priority, tags等（ユーザ定義）

        Raises:
            ValueError: シグナルが不正またはスキーマ違反の場合
        """
        ...
