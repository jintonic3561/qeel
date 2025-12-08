"""InMemoryStore実装

テスト用のインメモリストアを提供する。
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

import polars as pl

from qeel.models.context import Context


class ExchangeClientProtocol(Protocol):
    """ExchangeClientのプロトコル定義（型ヒント用）

    TODO(007): このプロトコルは007-exchange-client-and-mockブランチで
    qeel.exchange_clients.base.BaseExchangeClientが実装された際に削除し、
    そちらをimportして使用する。006での暫定措置。
    """

    def fetch_positions(self) -> pl.DataFrame | None:
        """現在のポジションを取得する"""
        ...


class InMemoryStore:
    """テスト用インメモリストア（最新のコンテキストのみ保持）

    ContextStoreと同じインターフェースを持つが、永続化せず最新のコンテキストのみ保持する。
    単体テストやインテグレーションテストで使用することを想定。
    日付パーティショニングは行わない。
    """

    def __init__(self) -> None:
        """インメモリストアを初期化"""
        self._signals: pl.DataFrame | None = None
        self._portfolio_plan: pl.DataFrame | None = None
        self._entry_orders: pl.DataFrame | None = None
        self._exit_orders: pl.DataFrame | None = None
        self._current_datetime: datetime | None = None

    def save_signals(self, target_datetime: datetime, signals: pl.DataFrame) -> None:
        """最新のシグナルのみ保持（上書き）

        Args:
            target_datetime: 保存する日付
            signals: シグナルDataFrame
        """
        self._signals = signals
        self._current_datetime = target_datetime

    def save_portfolio_plan(self, target_datetime: datetime, portfolio_plan: pl.DataFrame) -> None:
        """最新のポートフォリオ計画のみ保持（上書き）

        Args:
            target_datetime: 保存する日付
            portfolio_plan: ポートフォリオ計画DataFrame
        """
        self._portfolio_plan = portfolio_plan
        self._current_datetime = target_datetime

    def save_entry_orders(self, target_datetime: datetime, entry_orders: pl.DataFrame) -> None:
        """最新のエントリー注文のみ保持（上書き）

        Args:
            target_datetime: 保存する日付
            entry_orders: エントリー注文DataFrame
        """
        self._entry_orders = entry_orders
        self._current_datetime = target_datetime

    def save_exit_orders(self, target_datetime: datetime, exit_orders: pl.DataFrame) -> None:
        """最新のエグジット注文のみ保持（上書き）

        Args:
            target_datetime: 保存する日付
            exit_orders: エグジット注文DataFrame
        """
        self._exit_orders = exit_orders
        self._current_datetime = target_datetime

    def load(self, target_datetime: datetime, exchange_client: ExchangeClientProtocol) -> Context | None:
        """target_datetimeは無視し、最新のコンテキストを返す

        Args:
            target_datetime: 読み込む日付（無視される）
            exchange_client: ポジション取得用のExchangeClientインスタンス

        Returns:
            最新のコンテキスト。存在しない場合はNone
        """
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

    def load_latest(self, exchange_client: ExchangeClientProtocol) -> Context | None:
        """最新のコンテキストを返す（load()と同じ動作）

        Args:
            exchange_client: ポジション取得用のExchangeClientインスタンス

        Returns:
            最新のコンテキスト。存在しない場合はNone
        """
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
        """target_datetimeは無視し、コンテキストが存在するか確認

        Args:
            target_datetime: 確認する日付（無視される）

        Returns:
            コンテキストが存在する場合True
        """
        return self._current_datetime is not None
