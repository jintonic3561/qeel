# Contract: ContextStore

## 概要

コンテキスト（シグナル、ポートフォリオ計画、エントリー注文、エグジット注文）の保存・読み込みを担当する単一実装クラス。ポジション情報は`BaseExchangeClient`から動的に取得されるため、保存対象外。IOレイヤー（BaseIO）を経由してデータ読み書きを行い、データ参照先の判別はIOレイヤーに委譲する。

## クラス定義

```python
from datetime import datetime
import polars as pl

from qeel.io.base import BaseIO
from qeel.models import Context


class ContextStore:
    """コンテキスト永続化クラス（単一実装）

    iteration間でコンテキストの各要素を保存・復元する。
    日付ごとにパーティショニングされ、トレーサビリティを確保する。
    各ステップの出力（signals, portfolio_plan, entry_orders, exit_orders）を個別に保存することで、
    iteration内の段階的な状態を記録できる。
    current_positionsはBaseExchangeClient.fetch_positions()から動的に取得されるため保存対象外。

    IOレイヤー経由でデータ操作を行い、Local/S3の判別ロジックを持たない。
    """

    def __init__(self, io: BaseIO):
        """
        Args:
            io: IOレイヤー実装（LocalIO、S3IO等）
        """
        self.io = io
        self.base_path = io.get_base_path("outputs/context")

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
        partition_dir = self.io.get_partition_dir(self.base_path, target_datetime)
        date_str = target_datetime.strftime("%Y-%m-%d")
        path = f"{partition_dir}/signals_{date_str}.parquet"
        self.io.save(path, signals, format="parquet")

    def save_portfolio_plan(self, target_datetime: datetime, portfolio_plan: pl.DataFrame) -> None:
        """ポートフォリオ計画を日付ごとにパーティショニングして保存する

        Args:
            target_datetime: 保存する日付
            portfolio_plan: PortfolioSchemaに準拠したDataFrame

        Raises:
            RuntimeError: 保存失敗時
        """
        partition_dir = self.io.get_partition_dir(self.base_path, target_datetime)
        date_str = target_datetime.strftime("%Y-%m-%d")
        path = f"{partition_dir}/portfolio_plan_{date_str}.parquet"
        self.io.save(path, portfolio_plan, format="parquet")

    def save_entry_orders(self, target_datetime: datetime, entry_orders: pl.DataFrame) -> None:
        """エントリー注文を日付ごとにパーティショニングして保存する

        Args:
            target_datetime: 保存する日付
            entry_orders: OrderSchemaに準拠したDataFrame

        Raises:
            RuntimeError: 保存失敗時
        """
        partition_dir = self.io.get_partition_dir(self.base_path, target_datetime)
        date_str = target_datetime.strftime("%Y-%m-%d")
        path = f"{partition_dir}/entry_orders_{date_str}.parquet"
        self.io.save(path, entry_orders, format="parquet")

    def save_exit_orders(self, target_datetime: datetime, exit_orders: pl.DataFrame) -> None:
        """エグジット注文を日付ごとにパーティショニングして保存する

        Args:
            target_datetime: 保存する日付
            exit_orders: OrderSchemaに準拠したDataFrame

        Raises:
            RuntimeError: 保存失敗時
        """
        partition_dir = self.io.get_partition_dir(self.base_path, target_datetime)
        date_str = target_datetime.strftime("%Y-%m-%d")
        path = f"{partition_dir}/exit_orders_{date_str}.parquet"
        self.io.save(path, exit_orders, format="parquet")

    def load(self, target_datetime: datetime, exchange_client: "BaseExchangeClient") -> Context | None:
        """指定日付のコンテキストを読み込む

        Args:
            target_datetime: 読み込む日付
            exchange_client: ポジション取得用のExchangeClientインスタンス

        Returns:
            保存されたコンテキスト。指定日付で利用可能な要素（signals, portfolio_plan, entry_orders, exit_orders）を
            ストレージから読み込み、current_positionsはexchange_client.fetch_positions()から取得して
            Contextに格納。保存された要素が存在しない場合はNone。

        Raises:
            RuntimeError: 読み込み失敗時（破損など）
        """
        partition_dir = self.io.get_partition_dir(self.base_path, target_datetime)
        date_str = target_datetime.strftime("%Y-%m-%d")

        signals = self.io.load(f"{partition_dir}/signals_{date_str}.parquet", format="parquet")
        portfolio_plan = self.io.load(f"{partition_dir}/portfolio_plan_{date_str}.parquet", format="parquet")
        entry_orders = self.io.load(f"{partition_dir}/entry_orders_{date_str}.parquet", format="parquet")
        exit_orders = self.io.load(f"{partition_dir}/exit_orders_{date_str}.parquet", format="parquet")

        current_positions = exchange_client.fetch_positions()

        if any([signals is not None, portfolio_plan is not None, entry_orders is not None, exit_orders is not None]):
            return Context(
                current_datetime=target_datetime,
                signals=signals,
                portfolio_plan=portfolio_plan,
                entry_orders=entry_orders,
                exit_orders=exit_orders,
                current_positions=current_positions,
            )
        return None

    def load_latest(self, exchange_client: "BaseExchangeClient") -> Context | None:
        """最新日付のコンテキストを読み込む

        Args:
            exchange_client: ポジション取得用のExchangeClientインスタンス

        Returns:
            最新のコンテキスト。存在しない場合はNone

        Raises:
            RuntimeError: 読み込み失敗時（破損など）
        """
        target_datetime = self._find_latest_datetime()
        if target_datetime is None:
            return None
        return self.load(target_datetime, exchange_client)

    def exists(self, target_datetime: datetime) -> bool:
        """指定日付のコンテキストが存在するか確認

        Args:
            target_datetime: 確認する日付

        Returns:
            コンテキストが保存されている場合True
        """
        partition_dir = self.io.get_partition_dir(self.base_path, target_datetime)
        date_str = target_datetime.strftime("%Y-%m-%d")

        return any([
            self.io.exists(f"{partition_dir}/signals_{date_str}.parquet"),
            self.io.exists(f"{partition_dir}/portfolio_plan_{date_str}.parquet"),
            self.io.exists(f"{partition_dir}/entry_orders_{date_str}.parquet"),
            self.io.exists(f"{partition_dir}/exit_orders_{date_str}.parquet"),
        ])

    def _find_latest_datetime(self) -> datetime | None:
        """保存されているファイルから最新日付を探索

        実装詳細は省略（IOレイヤーを使ってパーティション探索）
        """
        # TODO: 実装
        ...
```

## テスタビリティ

- `InMemoryStore` をテスト用に実装可能（日付パーティショニングなし、最新のみ保持）:

```python
from datetime import datetime

import polars as pl

from qeel.models import Context
from qeel.stores import BaseContextStore


class InMemoryStore(BaseContextStore):
    """テスト用インメモリストア（最新のコンテキストのみ保持）"""

    def __init__(self):
        self._signals: pl.DataFrame | None = None
        self._portfolio_plan: pl.DataFrame | None = None
        self._entry_orders: pl.DataFrame | None = None
        self._exit_orders: pl.DataFrame | None = None
        self._current_datetime: datetime | None = None

    def save_signals(self, target_datetime: datetime, signals: pl.DataFrame) -> None:
        """最新のシグナルのみ保持（上書き）"""
        self._signals = signals
        self._current_datetime = target_datetime

    def save_portfolio_plan(self, target_datetime: datetime, portfolio_plan: pl.DataFrame) -> None:
        """最新のポートフォリオ計画のみ保持（上書き）"""
        self._portfolio_plan = portfolio_plan
        self._current_datetime = target_datetime

    def save_entry_orders(self, target_datetime: datetime, entry_orders: pl.DataFrame) -> None:
        """最新のエントリー注文のみ保持（上書き）"""
        self._entry_orders = entry_orders
        self._current_datetime = target_datetime

    def save_exit_orders(self, target_datetime: datetime, exit_orders: pl.DataFrame) -> None:
        """最新のエグジット注文のみ保持（上書き）"""
        self._exit_orders = exit_orders
        self._current_datetime = target_datetime

    def load(self, target_datetime: datetime, exchange_client) -> Context | None:
        """target_datetimeは無視し、最新のコンテキストを返す"""
        if self._current_datetime is None:
            return None

        # ポジションはExchangeClientから動的に取得
        current_positions = exchange_client.fetch_positions()

        return Context(
            current_datetime=self._current_datetime,
            signals=self._signals,
            portfolio_plan=self._portfolio_plan,
            entry_orders=self._entry_orders,
            exit_orders=self._exit_orders,
            current_positions=current_positions,
        )

    def load_latest(self, exchange_client) -> Context | None:
        """最新のコンテキストを返す（load()と同じ動作）"""
        if self._current_datetime is None:
            return None

        # ポジションはExchangeClientから動的に取得
        current_positions = exchange_client.fetch_positions()

        return Context(
            current_datetime=self._current_datetime,
            signals=self._signals,
            portfolio_plan=self._portfolio_plan,
            entry_orders=self._entry_orders,
            exit_orders=self._exit_orders,
            current_positions=current_positions,
        )

    def exists(self, target_datetime: datetime) -> bool:
        """target_datetimeは無視し、コンテキストが存在するか確認"""
        return self._current_datetime is not None
```
