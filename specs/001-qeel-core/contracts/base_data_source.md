# Contract: BaseDataSource

## 概要

ユーザがデータソース（Parquet、API、データベース等）からMarketDataを取得するロジックを実装するための抽象基底クラス。

## インターフェース定義

```python
from abc import ABC, abstractmethod
from datetime import datetime
import polars as pl
from qeel.config import DataSourceConfig

class BaseDataSource(ABC):
    """データソース抽象基底クラス

    ユーザはこのクラスを継承し、fetch()メソッドを実装する。

    Attributes:
        config: DataSourceConfig（toml設定から生成）
    """

    def __init__(self, config: DataSourceConfig):
        """
        Args:
            config: データソース設定
        """
        self.config = config

    @abstractmethod
    def fetch(self, start: datetime, end: datetime, symbols: list[str]) -> pl.DataFrame:
        """指定期間・銘柄のデータを取得する

        Args:
            start: 開始日時
            end: 終了日時
            symbols: 銘柄コードリスト

        Returns:
            MarketDataSchemaに準拠したPolars DataFrame

        Raises:
            ValueError: データ取得失敗またはスキーマ不正の場合
        """
        ...
```

## 実装例

### Parquetファイルからの読み込み（標準実装）

```python
import polars as pl
from qeel.data_sources import BaseDataSource
from qeel.schemas import MarketDataSchema

class ParquetDataSource(BaseDataSource):
    """Parquetファイルから MarketDataを読み込む（標準実装）

    ParquetはCSVと比較して以下の利点があります：
    - 型情報を保持（datetime, float等が自動認識）
    - カラムナーフォーマットで高速読み込み
    - 圧縮効率が良い（ファイルサイズ削減）
    - ゼロコピー読み込み（メモリ効率）
    """

    def fetch(self, start: datetime, end: datetime, symbols: list[str]) -> pl.DataFrame:
        # Parquetファイルを読み込み（型情報が保持される）
        df = pl.read_parquet(self.config.source_path)

        # datetime列の正規化
        if self.config.datetime_column != "datetime":
            if df[self.config.datetime_column].dtype != pl.Datetime:
                df = df.with_columns([
                    pl.col(self.config.datetime_column).cast(pl.Datetime).alias("datetime")
                ])
            else:
                df = df.rename({self.config.datetime_column: "datetime"})

        # フィルタリング（Polarsのlazyクエリで最適化）
        df = df.filter(
            (pl.col("datetime") >= start) &
            (pl.col("datetime") <= end) &
            (pl.col("symbol").is_in(symbols))
        )

        # オフセット適用（データ利用可能時刻を調整）
        if self.config.offset_seconds != 0:
            df = df.with_columns([
                (pl.col("datetime") + pl.duration(seconds=self.config.offset_seconds)).alias("datetime")
            ])

        return MarketDataSchema.validate(df)
```

## 契約事項

### 入力

- `start`, `end`: 取得するデータの範囲（iteration日時 + window）
- `symbols`: 対象銘柄リスト
  - エンジンがiteration時に自動決定し、引数として渡される
  - `LoopConfig.universe`が指定されている場合、そのリストと当日データが存在する銘柄の積集合
  - `LoopConfig.universe`が`None`の場合、データソース内で当日データが存在するすべての銘柄
  - ユーザはこの引数を受け取り、データソースから該当銘柄のみを取得する

### 出力

- 必ず `MarketDataSchema` に準拠したDataFrameを返す
- 必須列: `datetime`, `symbol`, `close`
- データが存在しない場合は空のDataFrameを返す（エラーにしない）

### データ欠損処理

- データソース内にNaN/nullが含まれる場合、そのまま返す
- 欠損処理はシグナル計算ロジック内でユーザが実施

### テスタビリティ

- モックデータを返すテスト用DataSourceを簡単に実装可能
- `config` はPydanticモデルなのでテスト時に設定変更が型安全

## 標準実装

Qeelは以下の標準実装を提供する：

- `ParquetDataSource`: Parquetファイル読み込み（**推奨標準実装**）
  - 型情報保持、高速、圧縮効率が良い
  - CSVより優れているため、Parquetのみを標準実装として提供
- `MockDataSource`: テスト用モックデータ

ユーザは独自のデータソース（API、データベース等）を自由に実装可能。
