"""シグナル計算抽象基底クラス

contracts/base_signal_calculator.mdの仕様に準拠。
ユーザはこのクラスを継承し、calculate()メソッドを実装する。
"""

from abc import ABC, abstractmethod

import polars as pl

from qeel.config.params import SignalCalculatorParams
from qeel.schemas.validators import SignalSchema


class BaseSignalCalculator(ABC):
    """シグナル計算抽象基底クラス

    ユーザはこのクラスを継承し、calculate()メソッドを実装する。

    Attributes:
        params: SignalCalculatorParamsを継承したPydanticモデル

    Example:
        class MySignalCalculator(BaseSignalCalculator):
            def calculate(self, data_sources: dict[str, pl.DataFrame]) -> pl.DataFrame:
                ohlcv = data_sources["ohlcv"]
                # シグナル計算ロジック
                return signals
    """

    def __init__(self, params: SignalCalculatorParams) -> None:
        """
        Args:
            params: シグナル計算パラメータ（Pydanticモデル）
        """
        self.params = params

    def _validate_output(self, signals: pl.DataFrame) -> pl.DataFrame:
        """出力シグナルの共通バリデーション

        サブクラスで任意に呼び出し可能なヘルパーメソッド。
        スキーマバリデーションを一箇所で実行し、重複を避ける。

        Args:
            signals: シグナルDataFrame（SignalSchema準拠）

        Returns:
            バリデーション済みのDataFrame

        Raises:
            ValueError: スキーマ違反の場合
        """
        return SignalSchema.validate(signals)

    @abstractmethod
    def calculate(self, data_sources: dict[str, pl.DataFrame]) -> pl.DataFrame:
        """シグナルを計算する

        Args:
            data_sources: データソース名をキーとするPolars DataFrameの辞書
                         各DataFrameは`datetime`列を必須とし、それ以外の列スキーマは
                         データソースごとに任意

        Returns:
            シグナルDataFrame（SignalSchemaに準拠）
            必須列: datetime (pl.Datetime), symbol (pl.String)
            オプション列: signal (pl.Float64) または任意のシグナル列
                         （例: signal_momentum, signal_value等）

        Raises:
            ValueError: データソースが不足している、またはスキーマ不正の場合
        """
        ...
