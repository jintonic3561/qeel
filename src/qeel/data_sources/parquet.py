"""ParquetDataSource実装

Parquetファイルからデータを読み込む標準実装。
contracts/base_data_source.mdを参照。
"""

from datetime import datetime

import polars as pl

from qeel.config import DataSourceConfig
from qeel.data_sources.base import BaseDataSource
from qeel.io.base import BaseIO


class ParquetDataSource(BaseDataSource):
    """Parquetファイルからデータを読み込む実装

    BaseDataSourceの共通ヘルパーメソッドとIOレイヤーを活用することで、
    簡潔で可読性の高い実装が可能。

    source_pathの指定方法:
        - 単一ファイル: "ohlcv.parquet"
        - globパターン: "ohlcv/*.parquet", "ohlcv/**/*.parquet"
        - Hiveパーティショニング: "ohlcv/" (year=2024/month=01/形式を自動認識)

    ローカル/S3の両方に対応（IOレイヤーが抽象化）。

    Attributes:
        config: データソース設定
        io: IOレイヤー実装（必須）
    """

    def __init__(self, config: DataSourceConfig, io: BaseIO | None = None) -> None:
        """ParquetDataSourceを初期化する

        Args:
            config: データソース設定
            io: IOレイヤー実装（必須）

        Raises:
            ValueError: ioがNoneの場合
        """
        super().__init__(config=config, io=io)
        if io is None:
            raise ValueError("ParquetDataSourceにはIOレイヤー（io）が必須です")

    def fetch(self, start: datetime, end: datetime, symbols: list[str]) -> pl.DataFrame:
        """指定期間・銘柄のデータをParquetファイルから取得する

        Args:
            start: 開始日時
            end: 終了日時
            symbols: 銘柄コードリスト

        Returns:
            Polars DataFrame（datetime, symbol列と指定された追加列）

        Raises:
            ValueError: データソースが見つからない場合
        """
        # IOレイヤー経由でParquetファイルを読み込み
        # globパターン、Hiveパーティショニングは自動的にPolarsが処理
        if self.io is None:
            raise ValueError("IOレイヤーが設定されていません")

        base_path = self.io.get_base_path("inputs")
        full_path = f"{base_path}/{self.config.source_path}"
        df = self.io.load(full_path, format="parquet")

        if df is None or (isinstance(df, pl.DataFrame) and df.is_empty()):
            raise ValueError(f"データソースが見つかりません: {full_path}")

        # dictが返った場合はDataFrameに変換不可のためエラー
        if not isinstance(df, pl.DataFrame):
            raise ValueError(f"Parquetデータの読み込みに失敗しました: {full_path}")

        # 共通ヘルパーメソッドを使用した前処理
        df = self._normalize_datetime_column(df)

        # offset_secondsを考慮してwindowを調整
        adjusted_start, adjusted_end = self._adjust_window_for_offset(start, end)

        # フィルタリング
        df = self._filter_by_datetime_and_symbols(df, adjusted_start, adjusted_end, symbols)

        return df
