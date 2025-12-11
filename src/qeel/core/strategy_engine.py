"""StrategyEngine実装

バックテストと実運用で共通のステップ単位実行エンジンを提供する。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from qeel.calculators.signals.base import BaseSignalCalculator
    from qeel.config import Config, DataSourceConfig
    from qeel.data_sources.base import BaseDataSource
    from qeel.entry_order_creators.base import BaseEntryOrderCreator
    from qeel.exchange_clients.base import BaseExchangeClient
    from qeel.exit_order_creators.base import BaseExitOrderCreator
    from qeel.portfolio_constructors.base import BasePortfolioConstructor
    from qeel.stores.context_store import ContextStore
    from qeel.stores.in_memory import InMemoryStore

from qeel.models.context import Context


class StepName(Enum):
    """StrategyEngineで使用するステップ名

    各ステップは独立して実行可能であり、
    実運用では外部スケジューラから個別に呼び出せる。
    """

    CALCULATE_SIGNALS = "calculate_signals"
    CONSTRUCT_PORTFOLIO = "construct_portfolio"
    CREATE_ENTRY_ORDERS = "create_entry_orders"
    CREATE_EXIT_ORDERS = "create_exit_orders"
    SUBMIT_ENTRY_ORDERS = "submit_entry_orders"
    SUBMIT_EXIT_ORDERS = "submit_exit_orders"


class StrategyEngineError(Exception):
    """StrategyEngineの実行エラー

    ステップ実行中に発生したエラーをラップし、デバッグ情報を提供する。

    Attributes:
        message: エラーメッセージ
        step_name: エラーが発生したステップ名
        target_date: ターゲット日時
        original_error: 元の例外（オプション）
    """

    def __init__(
        self,
        message: str,
        step_name: StepName,
        target_date: datetime,
        original_error: Exception | None = None,
    ) -> None:
        self.message = message
        self.step_name = step_name
        self.target_date = target_date
        self.original_error = original_error
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """エラーメッセージをフォーマットする"""
        date_str = self.target_date.strftime("%Y-%m-%d %H:%M:%S")
        msg = f"[{self.step_name.value}] {date_str}: {self.message}"
        if self.original_error:
            msg += f"\n  原因: {self.original_error}"
        return msg


class StrategyEngine:
    """StrategyEngine（ステップ単位実行エンジン）

    バックテストと実運用で同一のステップ実行ロジックを共有する。
    各ステップは独立して実行可能であり、実運用では外部スケジューラ
    （cron、Lambda等）から個別にステップを呼び出せる。

    Attributes:
        config: Qeel設定
        data_sources: データソース辞書（キー: データソース名）
        signal_calculator: シグナル計算クラス
        portfolio_constructor: ポートフォリオ構築クラス
        entry_order_creator: エントリー注文生成クラス
        exit_order_creator: エグジット注文生成クラス
        exchange_client: 取引所クライアント
        context_store: コンテキストストア
    """

    def __init__(
        self,
        config: Config,
        data_sources: dict[str, BaseDataSource],
        signal_calculator: BaseSignalCalculator,
        portfolio_constructor: BasePortfolioConstructor,
        entry_order_creator: BaseEntryOrderCreator,
        exit_order_creator: BaseExitOrderCreator,
        exchange_client: BaseExchangeClient,
        context_store: ContextStore | InMemoryStore,
    ) -> None:
        """StrategyEngineを初期化する

        Args:
            config: Qeel設定
            data_sources: データソース辞書（キー: データソース名、"ohlcv"必須）
            signal_calculator: シグナル計算クラス
            portfolio_constructor: ポートフォリオ構築クラス
            entry_order_creator: エントリー注文生成クラス
            exit_order_creator: エグジット注文生成クラス
            exchange_client: 取引所クライアント
            context_store: コンテキストストア（ContextStoreまたはInMemoryStore）
        """
        self.config = config
        self.data_sources = data_sources
        self.signal_calculator = signal_calculator
        self.portfolio_constructor = portfolio_constructor
        self.entry_order_creator = entry_order_creator
        self.exit_order_creator = exit_order_creator
        self.exchange_client = exchange_client
        self.context_store = context_store
        self._context: Context | None = None

    # データ取得期間計算

    def _get_data_fetch_range(
        self,
        target_date: datetime,
        ds_config: DataSourceConfig,
    ) -> tuple[datetime, datetime]:
        """データ取得期間を計算する

        Args:
            target_date: ターゲット日時
            ds_config: データソース設定

        Returns:
            (start, end)タプル
        """
        offset = timedelta(seconds=ds_config.offset_seconds)
        window = timedelta(seconds=ds_config.window_seconds)
        end = target_date - offset
        start = end - window
        return (start, end)

    def _fetch_data_sources(self, target_date: datetime) -> dict[str, pl.DataFrame]:
        """全データソースからデータを取得する

        Args:
            target_date: ターゲット日時

        Returns:
            データソース名をキーとするDataFrame辞書
        """
        result: dict[str, pl.DataFrame] = {}
        universe = self.config.loop.universe or []

        for name, ds in self.data_sources.items():
            start, end = self._get_data_fetch_range(target_date, ds.config)
            result[name] = ds.fetch(start, end, universe)

        return result

    def _fetch_ohlcv_for_step(self, target_date: datetime) -> pl.DataFrame:
        """OHLCVデータを取得する（注文生成ステップ用）

        Args:
            target_date: ターゲット日時

        Returns:
            OHLCVデータのDataFrame
        """
        ohlcv_ds = self.data_sources["ohlcv"]
        start, end = self._get_data_fetch_range(target_date, ohlcv_ds.config)
        universe = self.config.loop.universe or []
        return ohlcv_ds.fetch(start, end, universe)

    # 各ステップの実行メソッド

    def _run_calculate_signals(self, target_date: datetime) -> None:
        """シグナル計算ステップを実行する"""
        if self._context is None:
            raise StrategyEngineError(
                message="Contextが初期化されていません",
                step_name=StepName.CALCULATE_SIGNALS,
                target_date=target_date,
            )

        try:
            data_dict = self._fetch_data_sources(target_date)
            signals = self.signal_calculator.calculate(data_dict)

            self._context.signals = signals
            self.context_store.save_signals(target_date, signals)
        except StrategyEngineError:
            raise
        except Exception as e:
            raise StrategyEngineError(
                message="シグナル計算ステップでエラーが発生しました",
                step_name=StepName.CALCULATE_SIGNALS,
                target_date=target_date,
                original_error=e,
            ) from e

    def _run_construct_portfolio(self, target_date: datetime) -> None:
        """ポートフォリオ構築ステップを実行する"""
        if self._context is None:
            raise StrategyEngineError(
                message="Contextが初期化されていません",
                step_name=StepName.CONSTRUCT_PORTFOLIO,
                target_date=target_date,
            )
        if self._context.signals is None:
            raise StrategyEngineError(
                message="signalsが設定されていません。calculate_signalsステップを先に実行してください",
                step_name=StepName.CONSTRUCT_PORTFOLIO,
                target_date=target_date,
            )

        try:
            positions = self.exchange_client.fetch_positions()
            portfolio_plan = self.portfolio_constructor.construct(
                self._context.signals,
                positions,
            )

            self._context.portfolio_plan = portfolio_plan
            self.context_store.save_portfolio_plan(target_date, portfolio_plan)
        except StrategyEngineError:
            raise
        except Exception as e:
            raise StrategyEngineError(
                message="ポートフォリオ構築ステップでエラーが発生しました",
                step_name=StepName.CONSTRUCT_PORTFOLIO,
                target_date=target_date,
                original_error=e,
            ) from e

    def _run_create_entry_orders(self, target_date: datetime) -> None:
        """エントリー注文生成ステップを実行する"""
        if self._context is None:
            raise StrategyEngineError(
                message="Contextが初期化されていません",
                step_name=StepName.CREATE_ENTRY_ORDERS,
                target_date=target_date,
            )
        if self._context.portfolio_plan is None:
            raise StrategyEngineError(
                message="portfolio_planが設定されていません。construct_portfolioステップを先に実行してください",
                step_name=StepName.CREATE_ENTRY_ORDERS,
                target_date=target_date,
            )

        try:
            positions = self.exchange_client.fetch_positions()
            ohlcv = self._fetch_ohlcv_for_step(target_date)
            entry_orders = self.entry_order_creator.create(
                self._context.portfolio_plan,
                positions,
                ohlcv,
            )

            self._context.entry_orders = entry_orders
            self.context_store.save_entry_orders(target_date, entry_orders)
        except StrategyEngineError:
            raise
        except Exception as e:
            raise StrategyEngineError(
                message="エントリー注文生成ステップでエラーが発生しました",
                step_name=StepName.CREATE_ENTRY_ORDERS,
                target_date=target_date,
                original_error=e,
            ) from e

    def _run_create_exit_orders(self, target_date: datetime) -> None:
        """エグジット注文生成ステップを実行する"""
        if self._context is None:
            raise StrategyEngineError(
                message="Contextが初期化されていません",
                step_name=StepName.CREATE_EXIT_ORDERS,
                target_date=target_date,
            )

        try:
            positions = self.exchange_client.fetch_positions()
            ohlcv = self._fetch_ohlcv_for_step(target_date)
            exit_orders = self.exit_order_creator.create(positions, ohlcv)

            self._context.exit_orders = exit_orders
            self.context_store.save_exit_orders(target_date, exit_orders)
        except StrategyEngineError:
            raise
        except Exception as e:
            raise StrategyEngineError(
                message="エグジット注文生成ステップでエラーが発生しました",
                step_name=StepName.CREATE_EXIT_ORDERS,
                target_date=target_date,
                original_error=e,
            ) from e

    def _run_submit_entry_orders(self, target_date: datetime) -> None:
        """エントリー注文執行ステップを実行する"""
        if self._context is None:
            raise StrategyEngineError(
                message="Contextが初期化されていません",
                step_name=StepName.SUBMIT_ENTRY_ORDERS,
                target_date=target_date,
            )
        if self._context.entry_orders is None:
            raise StrategyEngineError(
                message="entry_ordersが設定されていません。create_entry_ordersステップを先に実行してください",
                step_name=StepName.SUBMIT_ENTRY_ORDERS,
                target_date=target_date,
            )

        try:
            if self._context.entry_orders.height > 0:
                self.exchange_client.submit_orders(self._context.entry_orders)
        except StrategyEngineError:
            raise
        except Exception as e:
            raise StrategyEngineError(
                message="エントリー注文執行ステップでエラーが発生しました",
                step_name=StepName.SUBMIT_ENTRY_ORDERS,
                target_date=target_date,
                original_error=e,
            ) from e

    def _run_submit_exit_orders(self, target_date: datetime) -> None:
        """エグジット注文執行ステップを実行する"""
        if self._context is None:
            raise StrategyEngineError(
                message="Contextが初期化されていません",
                step_name=StepName.SUBMIT_EXIT_ORDERS,
                target_date=target_date,
            )
        if self._context.exit_orders is None:
            raise StrategyEngineError(
                message="exit_ordersが設定されていません。create_exit_ordersステップを先に実行してください",
                step_name=StepName.SUBMIT_EXIT_ORDERS,
                target_date=target_date,
            )

        try:
            if self._context.exit_orders.height > 0:
                self.exchange_client.submit_orders(self._context.exit_orders)
        except StrategyEngineError:
            raise
        except Exception as e:
            raise StrategyEngineError(
                message="エグジット注文執行ステップでエラーが発生しました",
                step_name=StepName.SUBMIT_EXIT_ORDERS,
                target_date=target_date,
                original_error=e,
            ) from e

    # パブリックメソッド

    def run_step(self, target_date: datetime, step_name: StepName) -> None:
        """指定ステップを実行する

        Args:
            target_date: ターゲット日時
            step_name: 実行するステップ名

        Raises:
            ValueError: 不正なステップ名の場合
        """
        if not isinstance(step_name, StepName):
            raise ValueError(f"不正なステップ名です: {step_name}")

        # 常にcontextをロード（最新状態を保証）
        self.load_context(target_date)

        # Contextのcurrent_datetimeを更新
        self._context.current_datetime = target_date  # type: ignore[union-attr]

        # ステップに応じたメソッドを呼び出し
        step_handlers = {
            StepName.CALCULATE_SIGNALS: self._run_calculate_signals,
            StepName.CONSTRUCT_PORTFOLIO: self._run_construct_portfolio,
            StepName.CREATE_ENTRY_ORDERS: self._run_create_entry_orders,
            StepName.CREATE_EXIT_ORDERS: self._run_create_exit_orders,
            StepName.SUBMIT_ENTRY_ORDERS: self._run_submit_entry_orders,
            StepName.SUBMIT_EXIT_ORDERS: self._run_submit_exit_orders,
        }

        handler = step_handlers.get(step_name)
        if handler is None:
            raise ValueError(f"ハンドラが登録されていないステップです: {step_name}")
        handler(target_date)

    def run_steps(self, target_date: datetime, step_names: list[StepName]) -> None:
        """複数ステップを順番に実行する

        Args:
            target_date: ターゲット日時
            step_names: 実行するステップ名のリスト
        """
        for step_name in step_names:
            self.run_step(target_date, step_name)

    def load_context(self, target_date: datetime | None = None) -> Context:
        """コンテキストを読み込む

        Args:
            target_date: 読み込む日付（Noneの場合は最新）

        Returns:
            読み込んだContext、または新規Context
        """
        context: Context | None = None

        if target_date is not None:
            context = self.context_store.load(target_date, self.exchange_client)
        else:
            context = self.context_store.load_latest(self.exchange_client)

        # コンテキストが存在しない場合は新規作成
        if context is None:
            # target_dateがNoneの場合は現在時刻を使用
            current_dt = target_date if target_date is not None else datetime.now()
            context = Context(current_datetime=current_dt)

        self._context = context
        return context
