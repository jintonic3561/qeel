"""データソース抽象基底クラス

ユーザがデータソース（Parquet、API、データベース等）からデータを取得する
ロジックを実装するための抽象基底クラス。共通の前処理ヘルパーメソッドを提供し、
ユーザは必要に応じて利用可能。

contracts/base_data_source.mdを参照。
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any

import polars as pl

from qeel.config import DataSourceConfig

# BaseIOは006-io-and-context-managementで実装予定
# 型ヒントはAnyで代用（006実装後にBaseIOに変更）
BaseIO = Any


class BaseDataSource(ABC):
    """データソース抽象基底クラス

    ユーザはこのクラスを継承し、fetch()メソッドを実装する。
    共通の前処理ヘルパーメソッドを提供し、ユーザは必要に応じて利用可能。

    Attributes:
        config: DataSourceConfig（toml設定から生成）
        io: BaseIO | None（IOレイヤー、データ読み込みに使用。API経由等ではNone）
    """

    def __init__(self, config: DataSourceConfig, io: BaseIO | None = None) -> None:
        """
        Args:
            config: データソース設定
            io: IOレイヤー実装（LocalIO、S3IO等）。Noneの場合はIOレイヤーを使用しない
        """
        self.config = config
        self.io = io

    @abstractmethod
    def fetch(self, start: datetime, end: datetime, symbols: list[str]) -> pl.DataFrame:
        """指定期間・銘柄のデータを取得する

        Args:
            start: 開始日時
            end: 終了日時
            symbols: 銘柄コードリスト

        Returns:
            Polars DataFrame（必須列: datetime, symbol; その他の列は任意）

        Raises:
            ValueError: データ取得失敗の場合
        """
        ...

    # 共通ヘルパーメソッド（ユーザは必要に応じて利用可能）

    def _normalize_datetime_column(self, df: pl.DataFrame) -> pl.DataFrame:
        """datetime列を正規化する

        config.datetime_columnで指定された列名を"datetime"に変換し、
        型がDatetimeでない場合はキャストする。

        Args:
            df: 元のDataFrame

        Returns:
            datetime列が正規化されたDataFrame

        Raises:
            KeyError: config.datetime_columnで指定された列がDataFrameに存在しない場合
        """
        datetime_column = self.config.datetime_column

        # 列が存在するか確認
        if datetime_column not in df.columns:
            raise KeyError(
                f"datetime_columnで指定された列'{datetime_column}'がDataFrameに存在しません。存在する列: {df.columns}"
            )

        # すでに"datetime"列名の場合は何もしない
        if datetime_column == "datetime":
            return df

        # 型がDatetimeでない場合はキャストしてリネーム
        if df[datetime_column].dtype != pl.Datetime:
            # 文字列の場合はstr.to_datetimeを使用、それ以外はcastを試行
            if df[datetime_column].dtype == pl.Utf8:
                df = df.with_columns(pl.col(datetime_column).str.to_datetime().alias("datetime")).drop(datetime_column)
            else:
                df = df.with_columns(pl.col(datetime_column).cast(pl.Datetime).alias("datetime")).drop(datetime_column)
        else:
            # リネームのみ
            df = df.rename({datetime_column: "datetime"})

        return df

    def _adjust_window_for_offset(self, start: datetime, end: datetime) -> tuple[datetime, datetime]:
        """offset_secondsを考慮してデータ取得windowを調整する

        オフセットを適用する際、datetime列を上書きするのではなく、
        取得するデータのwindow範囲を調整する。これによりリーク危険性を低減し、
        可読性を向上させる。

        Args:
            start: 元の開始日時
            end: 元の終了日時

        Returns:
            調整後の(start, end)タプル
        """
        offset = timedelta(seconds=self.config.offset_seconds)
        return (start - offset, end - offset)

    def _filter_by_datetime_and_symbols(
        self,
        df: pl.DataFrame,
        start: datetime,
        end: datetime,
        symbols: list[str],
    ) -> pl.DataFrame:
        """datetime範囲と銘柄でフィルタリングする

        Args:
            df: フィルタリング対象のDataFrame
            start: 開始日時
            end: 終了日時
            symbols: 銘柄コードリスト

        Returns:
            フィルタリング済みのDataFrame
        """
        return df.filter(
            (pl.col("datetime") >= start) & (pl.col("datetime") <= end) & (pl.col("symbol").is_in(symbols))
        )
