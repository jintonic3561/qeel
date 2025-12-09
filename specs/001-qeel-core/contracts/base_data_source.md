# Contract: BaseDataSource

## 概要

ユーザがデータソース（Parquet、API、データベース等）からデータを取得するロジックを実装するための抽象基底クラス。共通の前処理ヘルパーメソッドを提供し、ユーザは必要に応じて利用可能。

## インターフェース定義

```python
from abc import ABC, abstractmethod
from datetime import datetime, timedelta

import polars as pl

from qeel.config import DataSourceConfig


class BaseDataSource(ABC):
    """データソース抽象基底クラス

    ユーザはこのクラスを継承し、fetch()メソッドを実装する。
    共通の前処理ヘルパーメソッドを提供し、ユーザは必要に応じて利用可能。

    Attributes:
        config: DataSourceConfig（toml設定から生成）
        io: BaseIO | None（IOレイヤー、データ読み込みに使用。API経由等ではNone）
    """

    def __init__(self, config: DataSourceConfig, io: BaseIO | None = None):
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
        if self.config.datetime_column != "datetime":
            if df[self.config.datetime_column].dtype != pl.Datetime:
                df = df.with_columns([
                    pl.col(self.config.datetime_column).cast(pl.Datetime).alias("datetime")
                ])
            else:
                df = df.rename({self.config.datetime_column: "datetime"})
        return df

    def _adjust_window_for_offset(
        self, start: datetime, end: datetime
    ) -> tuple[datetime, datetime]:
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
        self, df: pl.DataFrame, start: datetime, end: datetime, symbols: list[str]
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
            (pl.col("datetime") >= start)
            & (pl.col("datetime") <= end)
            & (pl.col("symbol").is_in(symbols))
        )
```

## 実装例

### ヘルパーメソッドを使用したParquetデータソース実装

```python
import polars as pl

from qeel.data_sources import BaseDataSource


class ParquetDataSource(BaseDataSource):
    """Parquetファイルからデータを読み込む実装例

    BaseDataSourceの共通ヘルパーメソッドとIOレイヤーを活用することで、
    簡潔で可読性の高い実装が可能。

    source_pathの指定方法:
        - 単一ファイル: "ohlcv.parquet"
        - globパターン: "ohlcv/*.parquet", "ohlcv/**/*.parquet"
        - Hiveパーティショニング: "ohlcv/" (year=2024/month=01/形式を自動認識)

    ローカル/S3の両方に対応（IOレイヤーが抽象化）。
    """

    def fetch(self, start: datetime, end: datetime, symbols: list[str]) -> pl.DataFrame:
        # IOレイヤー経由でParquetファイルを読み込み
        # globパターン、Hiveパーティショニングは自動的にPolarsが処理
        base_path = self.io.get_base_path("inputs")
        full_path = f"{base_path}/{self.config.source_path}"
        df = self.io.load(full_path, format="parquet")

        if df is None or df.is_empty():
            raise ValueError(f"データソースが見つかりません: {full_path}")

        # 共通ヘルパーメソッドを使用した前処理
        df = self._normalize_datetime_column(df)

        # offset_secondsを考慮してwindowを調整
        adjusted_start, adjusted_end = self._adjust_window_for_offset(start, end)

        # フィルタリング
        df = self._filter_by_datetime_and_symbols(df, adjusted_start, adjusted_end, symbols)

        return df
```

### カスタム実装例（API経由でのデータ取得）

```python
import polars as pl

from qeel.data_sources import BaseDataSource


class APIDataSource(BaseDataSource):
    """API経由でデータを取得するカスタム実装例

    ユーザは独自のデータ取得ロジックを自由に実装可能。
    共通ヘルパーメソッドは必要に応じて利用する。
    IOレイヤーは使用しない（API経由でデータ取得するため）。
    """

    def fetch(self, start: datetime, end: datetime, symbols: list[str]) -> pl.DataFrame:
        # offset_secondsを考慮してwindowを調整
        adjusted_start, adjusted_end = self._adjust_window_for_offset(start, end)

        # API経由でデータ取得（ユーザ実装）
        raw_data = self._fetch_from_api(adjusted_start, adjusted_end, symbols)

        # DataFrameに変換
        df = pl.DataFrame(raw_data)

        # datetime列の正規化（ヘルパー使用）
        df = self._normalize_datetime_column(df)

        return df

    def _fetch_from_api(self, start: datetime, end: datetime, symbols: list[str]) -> list[dict]:
        """API経由でデータを取得する（ユーザ実装）"""
        # ユーザが独自のAPI呼び出しロジックを実装
        ...
```

### MockDataSource（テスト用）

```python
from datetime import datetime

import polars as pl

from qeel.data_sources import BaseDataSource


class MockDataSource(BaseDataSource):
    """テスト用モックデータソース

    共通ヘルパーメソッドの使用例としても参照可能。
    デフォルトで最小OHLCVスキーマ（datetime, symbol, open, high, low, close, volume）を持つ。
    """

    def fetch(self, start: datetime, end: datetime, symbols: list[str]) -> pl.DataFrame:
        """モックデータを生成して返す

        デフォルトで最小OHLCVスキーマ（datetime, symbol, open, high, low, close, volume）を持つ。
        """
        # モックデータ生成（最小OHLCVスキーマ）
        target_symbols = symbols[:2] if len(symbols) >= 2 else symbols
        mock_data = {
            "datetime": [start] * len(target_symbols),
            "symbol": target_symbols,
            "open": [99.0, 199.0][:len(target_symbols)],
            "high": [101.0, 201.0][:len(target_symbols)],
            "low": [98.0, 198.0][:len(target_symbols)],
            "close": [100.0, 200.0][:len(target_symbols)],
            "volume": [1000, 2000][:len(target_symbols)],
        }
        df = pl.DataFrame(mock_data)

        # 必要に応じてヘルパーメソッドを使用
        # （この例ではdatetime列はすでに正規化されているため不要）

        return df
```

## 契約事項

### 入力

- `start`, `end`: 取得するデータの範囲（iteration日時 + window）
- `symbols`: 対象銘柄リスト
  - エンジンがiteration時に決定し、引数として渡される
    - `LoopConfig.universe`が指定されている場合: そのリストが渡される
    - `LoopConfig.universe`が`None`の場合: 全銘柄が対象となる
  - data_sourceはこのリストでフィルタリングする
  - フィルタリングの結果、当日データが存在する銘柄のみが自然に残る
    - 結果として「configで指定された銘柄」と「当日データが存在する銘柄」の積集合になる

### 出力

- Polars DataFrameを返す
- 必須列: `datetime` (pl.Datetime)
- その他の列は任意（データソースの種類に依存）
  - 例: OHLCVデータの場合は `symbol`, `close`, `open`, `high`, `low`, `volume` 等
  - 例: 決算情報の場合は `symbol`, `earnings`, `revenue` 等
- データが存在しない場合は空のDataFrameを返す（エラーにしない）
- ユーザは任意のスキーマを返すことができ、システムは強制的なバリデーションを行わない

### データ欠損処理

- データソース内にNaN/nullが含まれる場合、そのまま返す
- 欠損処理はシグナル計算ロジック内でユーザが実施

### テスタビリティ

- モックデータを返すテスト用DataSourceを簡単に実装可能
- `config` はPydanticモデルなのでテスト時に設定変更が型安全

## 共通ヘルパーメソッドの利点

`BaseDataSource`が提供する共通ヘルパーメソッドを使用することで：

- **リーク防止**: `_adjust_window_for_offset()`により、datetime列を上書きせずにwindow調整でオフセットを適用し、リーク危険性を低減
- **可読性向上**: 共通処理を明示的なメソッド呼び出しで表現し、実装意図を明確化
- **DRY原則**: 複数のデータソース実装で共通処理を再利用可能

ユーザは独自のデータソース（API、データベース等）を自由に実装可能。ヘルパーメソッドは任意で利用可能であり、強制ではない。

## 標準実装

Qeelは以下の標準実装を提供する：

- `ParquetDataSource`: Parquetファイルからデータを読み込む標準実装
  - 単一ファイル、globパターン、Hiveパーティショニングに対応
  - ローカル/S3の両方に対応（IOレイヤーが抽象化）
- `MockDataSource`: テスト用モックデータ（共通ヘルパーメソッド使用例として参照可能）

### source_pathの指定例

```toml
# 単一ファイル
[[data_sources]]
name = "ohlcv"
source_path = "ohlcv.parquet"

# globパターン（複数ファイル）
[[data_sources]]
name = "ohlcv"
source_path = "ohlcv/*.parquet"

# 再帰的globパターン
[[data_sources]]
name = "ohlcv"
source_path = "ohlcv/**/*.parquet"

# Hiveパーティショニング（ディレクトリ指定で自動認識）
[[data_sources]]
name = "ohlcv"
source_path = "ohlcv/"
# inputs/ohlcv/year=2024/month=01/data.parquet 形式を自動認識
```
