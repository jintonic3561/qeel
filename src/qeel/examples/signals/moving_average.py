"""移動平均クロス戦略の実装例

contracts/base_signal_calculator.mdの実装例に基づく。
短期移動平均と長期移動平均のクロスでシグナルを生成する。
"""

import polars as pl
from pydantic import Field, model_validator

from qeel.calculators.signals.base import BaseSignalCalculator
from qeel.config.params import SignalCalculatorParams


class MovingAverageCrossParams(SignalCalculatorParams):
    """移動平均クロス戦略のパラメータ

    Attributes:
        short_window: 短期移動平均のウィンドウサイズ（> 0）
        long_window: 長期移動平均のウィンドウサイズ（> 0）

    制約:
        short_window < long_window であること（移動平均クロス戦略の前提条件）
    """

    short_window: int = Field(..., gt=0, description="短期移動平均のwindow")
    long_window: int = Field(..., gt=0, description="長期移動平均のwindow")

    @model_validator(mode="after")
    def validate_short_less_than_long(self) -> "MovingAverageCrossParams":
        """short_windowがlong_windowより小さいことを検証"""
        if self.short_window >= self.long_window:
            raise ValueError(
                f"short_windowはlong_windowより小さい必要があります: "
                f"short_window={self.short_window}, long_window={self.long_window}"
            )
        return self


class MovingAverageCrossCalculator(BaseSignalCalculator):
    """移動平均クロス戦略のシグナル計算

    短期移動平均と長期移動平均の差をシグナルとして出力する。
    正のシグナル: 短期MA > 長期MA（ゴールデンクロス傾向）
    負のシグナル: 短期MA < 長期MA（デッドクロス傾向）

    Note:
        このクラスは実装例として提供されており、ユーザは独自の
        シグナル計算ロジックをBaseSignalCalculatorを継承して実装できる。
    """

    params: MovingAverageCrossParams

    def calculate(self, data_sources: dict[str, pl.DataFrame]) -> pl.DataFrame:
        """OHLCVデータから移動平均クロスシグナルを計算する

        Args:
            data_sources: データソース辞書。"ohlcv"キーが必須

        Returns:
            シグナルDataFrame（datetime, symbol, signal列を含む）

        Raises:
            ValueError: ohlcvデータソースが不足している場合
        """
        # データソース取得
        if "ohlcv" not in data_sources:
            raise ValueError("ohlcvデータソースが必要です")

        ohlcv = data_sources["ohlcv"]

        # 銘柄ごとに移動平均を計算
        # Polarsのrolling_mean_byを使用してソート済みデータで計算
        signals = (
            ohlcv.sort(["symbol", "datetime"])
            .with_columns(
                [
                    pl.col("close").rolling_mean(window_size=self.params.short_window).over("symbol").alias("short_ma"),
                    pl.col("close").rolling_mean(window_size=self.params.long_window).over("symbol").alias("long_ma"),
                ]
            )
            .with_columns(
                [
                    # 短期MAと長期MAの差をシグナルとする
                    (pl.col("short_ma") - pl.col("long_ma")).alias("signal")
                ]
            )
            .select(["datetime", "symbol", "signal"])
        )

        # 共通バリデーションヘルパーを使用
        return self._validate_output(signals)
