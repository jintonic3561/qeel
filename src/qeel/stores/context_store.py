"""ContextStore実装

コンテキスト永続化クラスを提供する。
"""

from __future__ import annotations

import re
from datetime import datetime

import polars as pl

from qeel.exchange_clients.base import BaseExchangeClient
from qeel.io.base import BaseIO
from qeel.models.context import Context


class ContextStore:
    """コンテキスト永続化クラス（単一実装）

    iteration間でコンテキストの各要素を保存・復元する。
    日付ごとにパーティショニングされ、トレーサビリティを確保する。
    各ステップの出力（signals, portfolio_plan, entry_orders, exit_orders）を
    個別に保存することで、iteration内の段階的な状態を記録できる。
    current_positionsはBaseExchangeClient.fetch_positions()から動的に取得されるため
    保存対象外。

    IOレイヤー経由でデータ操作を行い、Local/S3の判別ロジックを持たない。
    """

    def __init__(self, io: BaseIO) -> None:
        """ContextStoreを初期化する

        Args:
            io: IOレイヤー実装（LocalIO、S3IO等）
        """
        self.io = io
        self.base_path = io.get_base_path("outputs/context")

    def _save_component(self, target_datetime: datetime, data: pl.DataFrame, component_name: str) -> None:
        """コンテキストの各要素を日付ごとにパーティショニングして保存する（内部共通処理）

        target_datetimeを元に年月でディレクトリ分割し、
        ファイル名に日付を含めて保存する
        （例: 2025/01/signals_2025-01-15.parquet）

        Args:
            target_datetime: 保存する日付
            data: 保存するDataFrame
            component_name: 要素名（signals, portfolio_plan, entry_orders, exit_orders）

        Raises:
            RuntimeError: 保存失敗時
        """
        partition_dir = self.io.get_partition_dir(self.base_path, target_datetime)
        date_str = target_datetime.strftime("%Y-%m-%d")
        path = f"{partition_dir}/{component_name}_{date_str}.parquet"
        self.io.save(path, data, format="parquet")

    def save_signals(self, target_datetime: datetime, signals: pl.DataFrame) -> None:
        """シグナルを保存する"""
        self._save_component(target_datetime, signals, "signals")

    def save_portfolio_plan(self, target_datetime: datetime, portfolio_plan: pl.DataFrame) -> None:
        """ポートフォリオ計画を保存する"""
        self._save_component(target_datetime, portfolio_plan, "portfolio_plan")

    def save_entry_orders(self, target_datetime: datetime, entry_orders: pl.DataFrame) -> None:
        """エントリー注文を保存する"""
        self._save_component(target_datetime, entry_orders, "entry_orders")

    def save_exit_orders(self, target_datetime: datetime, exit_orders: pl.DataFrame) -> None:
        """エグジット注文を保存する"""
        self._save_component(target_datetime, exit_orders, "exit_orders")

    def load(self, target_datetime: datetime, exchange_client: BaseExchangeClient) -> Context | None:
        """指定日付のコンテキストを読み込む

        Args:
            target_datetime: 読み込む日付
            exchange_client: ポジション取得用のExchangeClientインスタンス
                           fetch_positions()メソッドを持つ必要がある

        Returns:
            保存されたコンテキスト。指定日付で利用可能な要素
            （signals, portfolio_plan, entry_orders, exit_orders）を
            ストレージから読み込み、current_positionsはexchange_client.fetch_positions()
            から取得してContextに格納。保存された要素が存在しない場合はNone。

        Raises:
            RuntimeError: 読み込み失敗時（破損など）
        """
        partition_dir = self.io.get_partition_dir(self.base_path, target_datetime)
        date_str = target_datetime.strftime("%Y-%m-%d")

        signals_data = self.io.load(f"{partition_dir}/signals_{date_str}.parquet", format="parquet")
        portfolio_plan_data = self.io.load(f"{partition_dir}/portfolio_plan_{date_str}.parquet", format="parquet")
        entry_orders_data = self.io.load(f"{partition_dir}/entry_orders_{date_str}.parquet", format="parquet")
        exit_orders_data = self.io.load(f"{partition_dir}/exit_orders_{date_str}.parquet", format="parquet")

        # pl.DataFrame | dict | Noneをpl.DataFrame | Noneに変換
        signals = signals_data if isinstance(signals_data, pl.DataFrame) else None
        portfolio_plan = portfolio_plan_data if isinstance(portfolio_plan_data, pl.DataFrame) else None
        entry_orders = entry_orders_data if isinstance(entry_orders_data, pl.DataFrame) else None
        exit_orders = exit_orders_data if isinstance(exit_orders_data, pl.DataFrame) else None

        # ポジションはExchangeClientから動的に取得
        current_positions = exchange_client.fetch_positions()

        # 保存された要素が1つもない場合はNoneを返す
        if all(x is None for x in [signals, portfolio_plan, entry_orders, exit_orders]):
            return None

        return Context(
            current_datetime=target_datetime,
            signals=signals,
            portfolio_plan=portfolio_plan,
            entry_orders=entry_orders,
            exit_orders=exit_orders,
            current_positions=current_positions,
        )

    def load_latest(self, exchange_client: BaseExchangeClient) -> Context | None:
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

        return any(
            [
                self.io.exists(f"{partition_dir}/signals_{date_str}.parquet"),
                self.io.exists(f"{partition_dir}/portfolio_plan_{date_str}.parquet"),
                self.io.exists(f"{partition_dir}/entry_orders_{date_str}.parquet"),
                self.io.exists(f"{partition_dir}/exit_orders_{date_str}.parquet"),
            ]
        )

    def _find_latest_datetime(self) -> datetime | None:
        """保存されているファイルから最新日付を探索

        io.list_files()を使用してパーティション配下のファイルを探索し、
        ファイル名から日付を抽出して最新のものを返す。

        実装方針:
        1. io.list_files(base_path, pattern="signals_*.parquet")で全signalsファイルを取得
        2. ファイル名から日付をパース（signals_YYYY-MM-DD.parquet形式）
        3. 最新の日付を返す
        """
        files = self.io.list_files(self.base_path, pattern="signals_*.parquet")
        if not files:
            return None

        dates: list[datetime] = []
        date_pattern = re.compile(r"signals_(\d{4}-\d{2}-\d{2})\.parquet$")
        for file_path in files:
            match = date_pattern.search(file_path)
            if match:
                dates.append(datetime.strptime(match.group(1), "%Y-%m-%d"))

        return max(dates) if dates else None
