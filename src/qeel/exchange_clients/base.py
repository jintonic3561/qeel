"""取引所クライアント抽象基底クラス

注文の執行、約定情報の取得、ポジション情報の取得を抽象化するインターフェース。
バックテスト時はMockExchangeClient、実運用時はユーザ実装のクライアントを使用する。
"""

from abc import ABC, abstractmethod

import polars as pl


class BaseExchangeClient(ABC):
    """取引所クライアント抽象基底クラス

    バックテストではモック約定とポジション管理、実運用では取引所API呼び出しを実装する。
    """

    def _validate_orders(self, orders: pl.DataFrame) -> None:
        """注文DataFrameの共通バリデーション

        サブクラスで任意に呼び出し可能なヘルパーメソッド。
        スキーマバリデーションを一箇所で実行し、重複を避ける。

        Args:
            orders: 注文DataFrame（OrderSchema準拠）

        Raises:
            ValueError: スキーマ違反の場合
        """
        from qeel.schemas import OrderSchema

        OrderSchema.validate(orders)

    def _validate_fills(self, fills: pl.DataFrame) -> pl.DataFrame:
        """約定情報DataFrameの共通バリデーション

        サブクラスで任意に呼び出し可能なヘルパーメソッド。
        スキーマバリデーションを一箇所で実行し、重複を避ける。

        Args:
            fills: 約定情報DataFrame（FillReportSchema準拠）

        Returns:
            バリデーション済みのDataFrame

        Raises:
            ValueError: スキーマ違反の場合
        """
        from qeel.schemas import FillReportSchema

        return FillReportSchema.validate(fills)

    def _validate_positions(self, positions: pl.DataFrame) -> pl.DataFrame:
        """ポジション情報DataFrameの共通バリデーション

        サブクラスで任意に呼び出し可能なヘルパーメソッド。
        スキーマバリデーションを一箇所で実行し、重複を避ける。

        Args:
            positions: ポジション情報DataFrame（PositionSchema準拠）

        Returns:
            バリデーション済みのDataFrame

        Raises:
            ValueError: スキーマ違反の場合
        """
        from qeel.schemas import PositionSchema

        return PositionSchema.validate(positions)

    @abstractmethod
    def submit_orders(self, orders: pl.DataFrame) -> None:
        """注文を執行する

        Args:
            orders: OrderSchemaに準拠したPolars DataFrame

        Raises:
            ValueError: 注文が不正な場合（スキーマ違反、数量ゼロ等）
            RuntimeError: 実運用時のAPI呼び出しエラー（ユーザ実装で処理）
        """
        ...

    @abstractmethod
    def fetch_fills(self) -> pl.DataFrame:
        """約定情報を取得する

        Returns:
            FillReportSchemaに準拠したPolars DataFrame

        Raises:
            RuntimeError: 実運用時のAPI呼び出しエラー（ユーザ実装で処理）
        """
        ...

    @abstractmethod
    def fetch_positions(self) -> pl.DataFrame:
        """現在のポジションを取得する

        バックテスト: 約定履歴から計算した現在のポジションを返す
        実運用: 取引所APIから現在のポジションを取得して返す

        Returns:
            PositionSchemaに準拠したPolars DataFrame

        Raises:
            RuntimeError: 実運用時のAPI呼び出しエラー（ユーザ実装で処理）
        """
        ...
