# Contract: BaseContextStore

## 概要

コンテキスト（ポジション、選択銘柄、モデルパラメータ等）の保存・読み込みを抽象化するインターフェース。バックテスト時はローカルファイル、実運用時はS3やデータベースを使用する。

## インターフェース定義

```python
from abc import ABC, abstractmethod
from datetime import datetime
import polars as pl

class BaseContextStore(ABC):
    """コンテキスト永続化抽象基底クラス

    iteration間でコンテキストの各要素を保存・復元する。
    日付ごとにパーティショニングされ、トレーサビリティを確保する。
    各ステップの出力（signals, portfolio_plan, orders, current_positions）を
    個別に保存することで、iteration内の段階的な状態を記録できる。
    """

    @abstractmethod
    def save_signals(self, target_datetime: datetime, signals: pl.DataFrame) -> None:
        """シグナルを日付ごとにパーティショニングして保存する

        target_datetimeを元に年月でディレクトリ分割し、
        ファイル名に日付を含めて保存する
        （例: 2025/01/signals_2025-01-15.parquet）

        Args:
            target_datetime: 保存する日付
            signals: SignalSchemaに準拠したDataFrame

        Raises:
            RuntimeError: 保存失敗時
        """
        ...

    @abstractmethod
    def save_portfolio_plan(self, target_datetime: datetime, portfolio_plan: pl.DataFrame) -> None:
        """ポートフォリオ計画を日付ごとにパーティショニングして保存する

        Args:
            target_datetime: 保存する日付
            portfolio_plan: PortfolioSchemaに準拠したDataFrame

        Raises:
            RuntimeError: 保存失敗時
        """
        ...

    @abstractmethod
    def save_orders(self, target_datetime: datetime, orders: pl.DataFrame) -> None:
        """注文を日付ごとにパーティショニングして保存する

        Args:
            target_datetime: 保存する日付
            orders: OrderSchemaに準拠したDataFrame

        Raises:
            RuntimeError: 保存失敗時
        """
        ...

    @abstractmethod
    def save_positions(self, target_datetime: datetime, positions: pl.DataFrame) -> None:
        """ポジションを日付ごとにパーティショニングして保存する

        Args:
            target_datetime: 保存する日付
            current_positions: PositionSchemaに準拠したDataFrame

        Raises:
            RuntimeError: 保存失敗時
        """
        ...

    @abstractmethod
    def load(self, target_datetime: datetime) -> Context | None:
        """指定日付のコンテキストを読み込む

        Args:
            target_datetime: 読み込む日付

        Returns:
            保存されたコンテキスト。指定日付で利用可能な要素（signals, portfolio_plan,
            orders, current_positions）を読み込み、存在しない要素はNoneとしてContextに格納。
            いずれかの要素が存在する場合のみContextを構築して返す。
            すべて存在しない場合はNone。

        Raises:
            RuntimeError: 読み込み失敗時（破損など）
        """
        ...

    @abstractmethod
    def load_latest(self) -> Context | None:
        """最新日付のコンテキストを読み込む

        Returns:
            最新のコンテキスト。存在しない場合はNone

        Raises:
            RuntimeError: 読み込み失敗時（破損など）
        """
        ...

    @abstractmethod
    def exists(self, target_datetime: datetime) -> bool:
        """指定日付のコンテキストが存在するか確認

        Args:
            target_datetime: 確認する日付

        Returns:
            コンテキストが保存されている場合True
        """
        ...
```

## 実装例

### ローカルファイル保存（実装イメージ）

```python
from pathlib import Path
import json
import polars as pl
from datetime import datetime
from qeel.stores import BaseContextStore
from qeel.models import Context

class LocalStore(BaseContextStore):
    """ローカルファイルにコンテキストを保存

    パーティション構造: base_path/YYYY/MM/
    ファイル例:
      - signals_2025-01-15.parquet
      - portfolio_plan_2025-01-15.parquet
      - orders_2025-01-15.parquet
      - positions_2025-01-15.parquet
    """

    def __init__(self, base_path: Path):
        self.base_path = base_path

    def _get_partition_dir(self, target_datetime: datetime) -> Path:
        """年月パーティションディレクトリを取得する"""
        partition_dir = self.base_path / target_datetime.strftime("%Y") / target_datetime.strftime("%m")
        partition_dir.mkdir(parents=True, exist_ok=True)
        return partition_dir

    def save_signals(self, target_datetime: datetime, signals: pl.DataFrame) -> None:
        """シグナルをParquetで保存する"""
        partition_dir = self._get_partition_dir(target_datetime)
        date_str = target_datetime.strftime("%Y-%m-%d")
        signals.write_parquet(partition_dir / f"signals_{date_str}.parquet")

    def save_portfolio_plan(self, target_datetime: datetime, portfolio_plan: pl.DataFrame) -> None:
        """ポートフォリオ計画をParquetで保存する"""
        partition_dir = self._get_partition_dir(target_datetime)
        date_str = target_datetime.strftime("%Y-%m-%d")
        portfolio_plan.write_parquet(partition_dir / f"portfolio_plan_{date_str}.parquet")

    def save_orders(self, target_datetime: datetime, orders: pl.DataFrame) -> None:
        """注文をParquetで保存する"""
        partition_dir = self._get_partition_dir(target_datetime)
        date_str = target_datetime.strftime("%Y-%m-%d")
        orders.write_parquet(partition_dir / f"orders_{date_str}.parquet")

    def save_positions(self, target_datetime: datetime, positions: pl.DataFrame) -> None:
        """ポジションをParquetで保存する"""
        partition_dir = self._get_partition_dir(target_datetime)
        date_str = target_datetime.strftime("%Y-%m-%d")
        positions.write_parquet(partition_dir / f"positions_{date_str}.parquet")

    def load(self, target_datetime: datetime) -> Context | None:
        """指定日付のコンテキストを読み込む"""
        partition_dir = self.base_path / target_datetime.strftime("%Y") / target_datetime.strftime("%m")
        date_str = target_datetime.strftime("%Y-%m-%d")

        # 各要素をParquetから読み込み（存在しない場合はNone）
        signals = None
        signals_path = partition_dir / f"signals_{date_str}.parquet"
        if signals_path.exists():
            signals = pl.read_parquet(signals_path)

        portfolio_plan = None
        portfolio_path = partition_dir / f"portfolio_plan_{date_str}.parquet"
        if portfolio_path.exists():
            portfolio_plan = pl.read_parquet(portfolio_path)

        orders = None
        orders_path = partition_dir / f"orders_{date_str}.parquet"
        if orders_path.exists():
            orders = pl.read_parquet(orders_path)

        current_positions = None
        positions_path = partition_dir / f"positions_{date_str}.parquet"
        if positions_path.exists():
            current_positions = pl.read_parquet(positions_path)

        # いずれかの要素が存在する場合のみContextを構築
        if any([signals is not None, portfolio_plan is not None,
                orders is not None, current_positions is not None]):
            return Context(
                current_datetime=target_datetime,
                signals=signals,
                portfolio_plan=portfolio_plan,
                orders=orders,
                current_positions=current_positions,
            )
        return None

    def load_latest(self) -> Context | None:
        """最新日付のコンテキストを読み込む"""
        target_datetime = self._find_latest_datetime()
        if target_datetime is None:
            return None
        return self.load(target_datetime)

    def exists(self, target_datetime: datetime) -> bool:
        """コンテキストの存在確認"""
        partition_dir = self.base_path / target_datetime.strftime("%Y") / target_datetime.strftime("%m")
        date_str = target_datetime.strftime("%Y-%m-%d")

        # いずれかのファイルが存在すればTrue
        return any([
            (partition_dir / f"signals_{date_str}.parquet").exists(),
            (partition_dir / f"portfolio_plan_{date_str}.parquet").exists(),
            (partition_dir / f"orders_{date_str}.parquet").exists(),
            (partition_dir / f"positions_{date_str}.parquet").exists(),
        ])

    def _find_latest_datetime(self) -> datetime | None:
        """YYYY/MM/配下のファイル名から最新日付を探索"""
        # 実装省略
        ...
```

### S3保存（実装イメージ、実運用必須）

```python
import boto3
from io import BytesIO
from datetime import datetime
import polars as pl
from qeel.stores import BaseContextStore
from qeel.models import Context

class S3Store(BaseContextStore):
    """S3にコンテキストを保存（実運用必須）

    パーティション構造: s3://bucket/key_prefix/YYYY/MM/
    ファイル例:
      - signals_2025-01-15.parquet
      - portfolio_plan_2025-01-15.parquet
      - orders_2025-01-15.parquet
      - positions_2025-01-15.parquet
    """

    def __init__(self, bucket: str, key_prefix: str):
        self.bucket = bucket
        self.key_prefix = key_prefix.rstrip('/')
        self.s3_client = boto3.client('s3')

    def _get_partition_prefix(self, target_datetime: datetime) -> str:
        """年月パーティションプレフィックスを取得する"""
        return f"{self.key_prefix}/{target_datetime.strftime('%Y')}/{target_datetime.strftime('%m')}"

    def _save_dataframe(self, target_datetime: datetime, df: pl.DataFrame, name: str) -> None:
        """DataFrameをS3にParquetで保存する共通メソッド"""
        partition_prefix = self._get_partition_prefix(target_datetime)
        date_str = target_datetime.strftime("%Y-%m-%d")
        buffer = BytesIO()
        df.write_parquet(buffer)
        buffer.seek(0)
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=f"{partition_prefix}/{name}_{date_str}.parquet",
            Body=buffer.getvalue(),
        )

    def save_signals(self, target_datetime: datetime, signals: pl.DataFrame) -> None:
        """シグナルをS3にParquetで保存する"""
        self._save_dataframe(target_datetime, signals, "signals")

    def save_portfolio_plan(self, target_datetime: datetime, portfolio_plan: pl.DataFrame) -> None:
        """ポートフォリオ計画をS3にParquetで保存する"""
        self._save_dataframe(target_datetime, portfolio_plan, "portfolio_plan")

    def save_orders(self, target_datetime: datetime, orders: pl.DataFrame) -> None:
        """注文をS3にParquetで保存する"""
        self._save_dataframe(target_datetime, orders, "orders")

    def save_positions(self, target_datetime: datetime, positions: pl.DataFrame) -> None:
        """ポジションをS3にParquetで保存する"""
        self._save_dataframe(target_datetime, positions, "positions")

    def load(self, target_datetime: datetime) -> Context | None:
        """指定日付のコンテキストを読み込む"""
        partition_prefix = self._get_partition_prefix(target_datetime)
        date_str = target_datetime.strftime("%Y-%m-%d")

        # 各要素をS3から読み込み（存在しない場合はNone）
        signals = self._load_dataframe(partition_prefix, f"signals_{date_str}.parquet")
        portfolio_plan = self._load_dataframe(partition_prefix, f"portfolio_plan_{date_str}.parquet")
        orders = self._load_dataframe(partition_prefix, f"orders_{date_str}.parquet")
        positions = self._load_dataframe(partition_prefix, f"positions_{date_str}.parquet")

        # いずれかの要素が存在する場合のみContextを構築
        if any([signals is not None, portfolio_plan is not None,
                orders is not None, current_positions is not None]):
            return Context(
                current_datetime=target_datetime,
                signals=signals,
                portfolio_plan=portfolio_plan,
                orders=orders,
                current_positions=current_positions,
            )
        return None

    def load_latest(self) -> Context | None:
        """最新日付のコンテキストを読み込む"""
        target_datetime = self._find_latest_datetime()
        if target_datetime is None:
            return None
        return self.load(target_datetime)

    def _load_dataframe(self, partition_prefix: str, filename: str) -> pl.DataFrame | None:
        """S3からDataFrameを読み込む共通メソッド"""
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket,
                Key=f"{partition_prefix}/{filename}"
            )
            buffer = BytesIO(response['Body'].read())
            return pl.read_parquet(buffer)
        except self.s3_client.exceptions.NoSuchKey:
            return None

    def exists(self, target_datetime: datetime) -> bool:
        """コンテキストの存在確認"""
        partition_prefix = self._get_partition_prefix(target_datetime)
        date_str = target_datetime.strftime("%Y-%m-%d")

        # いずれかのファイルが存在すればTrue
        for name in ["signals", "portfolio_plan", "orders", "current_positions"]:
            try:
                self.s3_client.head_object(
                    Bucket=self.bucket,
                    Key=f"{partition_prefix}/{name}_{date_str}.parquet"
                )
                return True
            except self.s3_client.exceptions.ClientError:
                continue
        return False

    def _find_latest_datetime(self) -> datetime | None:
        """S3キー一覧からファイル名を解析して最新日付を探索"""
        # list_objects_v2で*.parquetを探索
        # 実装省略
        ...
```

## 契約事項

### save_signals / save_portfolio_plan / save_orders / save_positions

- 入力: `target_datetime: datetime`, `DataFrame` (対応するスキーマに準拠)
- `target_datetime`を元に年月でディレクトリパーティショニング（YYYY/MM/）
- 同一日付のデータは上書き、異なる日付は別ファイルとして保存（トレーサビリティ確保）
- DataFrameはParquet形式で保存される
- 保存失敗時はRuntimeErrorをraise
- 各ステップで独立して呼び出し可能（iteration内で段階的に保存できる）

### load

- 入力: `target_datetime: datetime`
- 出力: 保存された `Context` またはNone
- 指定日付で利用可能な要素（signals, portfolio_plan, orders, current_positions）を個別に読み込み、存在しない要素はNoneとしてContextに格納
- いずれかの要素が存在する場合のみContextを構築して返す（すべて存在しない場合はNone）
- 破損している場合はRuntimeErrorをraise

### load_latest

- 入力: なし
- 出力: 最新の `Context` またはNone
- 内部で`_find_latest_datetime()`を呼び出して最新日付を取得し、`load(target_datetime)`に委譲する
- コンテキストが存在しない場合はNone
- 破損している場合はRuntimeErrorをraise

### exists

- 入力: `target_datetime: datetime`
- コンテキストの存在チェック（いずれかのファイルが存在すればTrue）
- 高速に動作すること（実際の読み込みは行わない）

## テスタビリティ

- `InMemoryStore` をテスト用に実装可能（日付パーティショニングなし、最新のみ保持）:

```python
class InMemoryStore(BaseContextStore):
    def __init__(self):
        self._signals: pl.DataFrame | None = None
        self._portfolio_plan: pl.DataFrame | None = None
        self._orders: pl.DataFrame | None = None
        self._current_positions: pl.DataFrame | None = None
        self._current_datetime: datetime | None = None

    def save_signals(self, target_datetime: datetime, signals: pl.DataFrame) -> None:
        """最新のシグナルのみ保持（上書き）"""
        self._signals = signals
        self._current_datetime = target_datetime

    def save_portfolio_plan(self, target_datetime: datetime, portfolio_plan: pl.DataFrame) -> None:
        """最新のポートフォリオ計画のみ保持（上書き）"""
        self._portfolio_plan = portfolio_plan
        self._current_datetime = target_datetime

    def save_orders(self, target_datetime: datetime, orders: pl.DataFrame) -> None:
        """最新の注文のみ保持（上書き）"""
        self._orders = orders
        self._current_datetime = target_datetime

    def save_positions(self, target_datetime: datetime, positions: pl.DataFrame) -> None:
        """最新のポジションのみ保持（上書き）"""
        self._current_positions = positions
        self._current_datetime = target_datetime

    def load(self, target_datetime: datetime) -> Context | None:
        """target_datetimeは無視し、最新のコンテキストを返す"""
        if self._current_datetime is None:
            return None
        return Context(
            current_datetime=self._current_datetime,
            signals=self._signals,
            portfolio_plan=self._portfolio_plan,
            orders=self._orders,
            positions=self._current_positions,
        )

    def load_latest(self) -> Context | None:
        """最新のコンテキストを返す（load()と同じ動作）"""
        if self._current_datetime is None:
            return None
        return Context(
            current_datetime=self._current_datetime,
            signals=self._signals,
            portfolio_plan=self._portfolio_plan,
            orders=self._orders,
            positions=self._current_positions,
        )

    def exists(self, target_datetime: datetime) -> bool:
        """target_datetimeは無視し、コンテキストが存在するか確認"""
        return self._current_datetime is not None
```

## 標準実装

Qeelは以下の標準実装を提供する：

- `LocalStore(base_path)`: ローカルファイル保存（DataFrameは自動でParquet、日付パーティショニング、バックテスト用）
- `S3Store(bucket, key_prefix)`: S3保存（DataFrameは自動でParquet、日付パーティショニング、**実運用必須対応**、Branch 005で実装）
- `InMemoryStore()`: テスト用インメモリ保存（日付パーティショニングなし、最新のみ保持）

各実装は以下のメソッドを提供する：
- `save_signals()`, `save_portfolio_plan()`, `save_orders()`, `save_positions()`: iteration内の各ステップ出力を個別に保存
- `load(target_datetime)`: 指定日付のコンテキストを読み込み
- `load_latest()`: 最新日付のコンテキストを読み込み
- `exists(target_datetime)`: 指定日付のコンテキストが存在するか確認

ユーザは独自実装（データベース、他のクラウドストレージ等）を自由に追加可能。
