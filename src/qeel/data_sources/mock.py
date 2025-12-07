"""テスト用モックデータソース

共通ヘルパーメソッドの使用例としても参照可能。
デフォルトで最小OHLCVスキーマ（datetime, symbol, open, high, low, close, volume）を持つ。

contracts/base_data_source.mdを参照。
"""

from datetime import datetime

import polars as pl

from qeel.config import DataSourceConfig
from qeel.data_sources.base import BaseDataSource


class MockDataSource(BaseDataSource):
    """テスト用モックデータソース

    共通ヘルパーメソッドの使用例としても参照可能。
    デフォルトで最小OHLCVスキーマ（datetime, symbol, open, high, low, close, volume）を持つ。

    Attributes:
        _data: モックデータ（指定されない場合はデフォルトデータを生成）
    """

    def __init__(
        self,
        config: DataSourceConfig,
        data: pl.DataFrame | None = None,
    ) -> None:
        """
        Args:
            config: データソース設定
            data: モックデータ（Noneの場合はデフォルトデータを生成）
        """
        super().__init__(config=config)
        self._data = data

    def fetch(self, start: datetime, end: datetime, symbols: list[str]) -> pl.DataFrame:
        """モックデータをフィルタリングして返す

        Args:
            start: 開始日時
            end: 終了日時
            symbols: 銘柄コードリスト

        Returns:
            フィルタリング済みのPolars DataFrame
        """
        # データが指定されていない場合はデフォルトデータを生成
        if self._data is None:
            df = self._generate_default_data(start, symbols)
        else:
            df = self._data

        # ヘルパーメソッドを使用してフィルタリング
        df = self._filter_by_datetime_and_symbols(df, start, end, symbols)

        return df

    def _generate_default_data(self, start: datetime, symbols: list[str]) -> pl.DataFrame:
        """デフォルトのモックデータを生成する

        最小OHLCVスキーマ（datetime, symbol, open, high, low, close, volume）を持つ
        デフォルトデータを生成する。

        Args:
            start: 基準日時
            symbols: 銘柄コードリスト

        Returns:
            デフォルトモックデータのDataFrame
        """
        # 銘柄ごとにデフォルトデータを生成
        target_symbols = symbols if symbols else ["AAPL", "GOOG"]
        base_price = 100.0

        data: dict[str, list[datetime | str | float | int]] = {
            "datetime": [],
            "symbol": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": [],
        }

        for i, symbol in enumerate(target_symbols):
            price_offset = i * 100.0
            data["datetime"].append(start)
            data["symbol"].append(symbol)
            data["open"].append(base_price + price_offset - 1.0)
            data["high"].append(base_price + price_offset + 1.0)
            data["low"].append(base_price + price_offset - 2.0)
            data["close"].append(base_price + price_offset)
            data["volume"].append(1000 * (i + 1))

        return pl.DataFrame(data)
