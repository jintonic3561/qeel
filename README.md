# Qeel

量的トレーディング向けバックテストライブラリ。バックテストから実運用へのシームレスな接続を可能にする。

## 概要

Qeelは、クオンツアナリストが戦略の開発から実運用までを一貫して行えるPythonバックテストライブラリ。バックテストで検証したシグナル計算ロジックを、コードを変更することなく実運用環境に展開できる。

### 主要な特徴

- **バックテストと実運用の完全な再現性**: 同一のシグナル計算ロジック、ポートフォリオ構築ロジック、注文生成ロジックを使用
- **拡張性**: 抽象基底クラス（ABC）パターンで、ユーザが独自のロジックを実装可能
- **ステップ単位実行**: 各処理ステップを独立して実行可能、サーバーレス環境（Lambda等）対応
- **柔軟なストレージ**: ローカルファイルシステムとS3をサポート、簡単に切り替え可能

## インストール

### pipを使用する場合

```bash
pip install qeel
```

### uvを使用する場合

```bash
uv add qeel
```

## クイックスタート

### 1. ワークスペースの初期化

```bash
# 環境変数でワークスペースを指定（オプション）
export QEEL_WORKSPACE=/path/to/my_backtest

# ワークスペース構造を自動生成
qeel init
```

### 2. 設定ファイルの編集

`configs/config.toml` を編集して、データソース、コスト設定、ループ管理を定義します。

```toml
# General設定
[general]
storage_type = "local"  # "local" または "s3"

# ループ管理設定
[loop]
frequency = "1d"
start_date = "2023-01-01T00:00:00"
end_date = "2023-12-31T23:59:59"

# データソース定義
[[data_sources]]
name = "ohlcv"
datetime_column = "datetime"
offset_seconds = 0
window_seconds = 2592000  # 30日
source_type = "parquet"
source_path = "inputs/ohlcv.parquet"

# コスト設定
[costs]
commission_rate = 0.001  # 0.1%
slippage_bps = 5.0       # 5 bps
market_impact_model = "fixed"
market_impact_param = 0.0
```

### 3. シグナル計算ロジックの実装

```python
import polars as pl
from pydantic import BaseModel, Field
from qeel.calculators.signals.base import BaseSignalCalculator
from qeel.schemas import SignalSchema


class MovingAverageCrossParams(BaseModel):
    """移動平均クロス戦略のパラメータ"""
    short_window: int = Field(default=5, gt=0)
    long_window: int = Field(default=20, gt=0)


class MovingAverageCrossCalculator(BaseSignalCalculator):
    """移動平均クロス戦略のシグナル計算"""

    def calculate(self, data_sources: dict[str, pl.DataFrame]) -> pl.DataFrame:
        ohlcv = data_sources["ohlcv"]

        signals = (
            ohlcv
            .sort(["symbol", "datetime"])
            .with_columns([
                pl.col("close")
                  .rolling_mean(window_size=self.params.short_window)
                  .over("symbol")
                  .alias("short_ma"),
                pl.col("close")
                  .rolling_mean(window_size=self.params.long_window)
                  .over("symbol")
                  .alias("long_ma"),
            ])
            .with_columns([
                (pl.col("short_ma") - pl.col("long_ma")).alias("signal")
            ])
            .select(["datetime", "symbol", "signal"])
        )

        return SignalSchema.validate(signals)
```

### 4. バックテストの実行

```python
from pathlib import Path
from my_signal import MovingAverageCrossCalculator, MovingAverageCrossParams
from qeel.config import Config
from qeel.core.backtest_runner import BacktestRunner
from qeel.core.strategy_engine import StrategyEngine
from qeel.data_sources.parquet import ParquetDataSource
from qeel.entry_order_creators.equal_weight import EqualWeightEntryOrderCreator, EqualWeightEntryParams
from qeel.exchange_clients.mock import MockExchangeClient
from qeel.exit_order_creators.full_exit import FullExitOrderCreator, FullExitParams
from qeel.io.base import BaseIO
from qeel.portfolio_constructors.top_n import TopNPortfolioConstructor, TopNConstructorParams
from qeel.stores.context_store import ContextStore


def main():
    # 設定読み込み
    config = Config.from_toml(Path("configs/config.toml"))

    # IOレイヤーのセットアップ
    io = BaseIO.from_config(config.general)

    # シグナル計算クラスのインスタンス化
    signal_params = MovingAverageCrossParams(short_window=5, long_window=20)
    calculator = MovingAverageCrossCalculator(params=signal_params)

    # ポートフォリオ構築クラスのインスタンス化
    constructor_params = TopNConstructorParams(top_n=10)
    portfolio_constructor = TopNPortfolioConstructor(params=constructor_params)

    # エントリー注文生成クラスのインスタンス化
    entry_order_creator_params = EqualWeightEntryParams(capital=1_000_000.0)
    entry_order_creator = EqualWeightEntryOrderCreator(params=entry_order_creator_params)

    # エグジット注文生成クラスのインスタンス化
    exit_order_creator_params = FullExitParams(exit_threshold=1.0)
    exit_order_creator = FullExitOrderCreator(params=exit_order_creator_params)

    # データソースのセットアップ
    data_sources = {}
    for ds_config in config.data_sources:
        if ds_config.source_type == "parquet":
            data_sources[ds_config.name] = ParquetDataSource(ds_config, io)

    # 執行クラス（バックテストではモック）
    exchange_client = MockExchangeClient(config.costs)

    # コンテキストストア
    context_store = ContextStore(io)

    # StrategyEngine構築
    engine = StrategyEngine(
        calculator=calculator,
        portfolio_constructor=portfolio_constructor,
        entry_order_creator=entry_order_creator,
        exit_order_creator=exit_order_creator,
        data_sources=data_sources,
        exchange_client=exchange_client,
        context_store=context_store,
        config=config,
    )

    # BacktestRunner構築
    runner = BacktestRunner(engine=engine, config=config)

    # バックテスト実行
    print("バックテスト開始...")
    results = runner.run()

    # 結果表示
    print("\n=== バックテスト結果 ===")
    print(results.metrics)


if __name__ == "__main__":
    main()
```

### 5. 実運用への転用

バックテストと同じシグナル計算ロジックを使用し、`StrategyEngine` のステップ単位実行機能を利用して実運用に転用できる。

```python
from datetime import datetime
from qeel.core.strategy_engine import StrategyEngine
from qeel.examples.exchange_clients.exchange_api import ExchangeAPIClient

# 実運用用設定（storage_type="s3"）
io = BaseIO.from_config(config.general)

# 実運用用の執行クライアント
exchange_client = ExchangeAPIClient(api_client=my_api_client)

# StrategyEngine（バックテストと同一）
engine = StrategyEngine(
    calculator=calculator,  # バックテストと同じクラス
    portfolio_constructor=portfolio_constructor,
    entry_order_creator=entry_order_creator,
    exit_order_creator=exit_order_creator,
    data_sources=data_sources,
    exchange_client=exchange_client,
    context_store=context_store,
    config=config,
)

# 外部スケジューラから各ステップを独立して実行
today = datetime.now().date()
engine.run_step(today, "calculate_signals")  # 09:00に実行
engine.run_step(today, "construct_portfolio")  # 10:00に実行
engine.run_step(today, "create_entry_orders")  # 14:00に実行
engine.run_step(today, "create_exit_orders")  # 14:05に実行
engine.run_step(today, "submit_entry_orders")  # 15:00に実行
engine.run_step(today, "submit_exit_orders")  # 15:05に実行
```

## プロジェクト構造

```text
src/qeel/
├── __init__.py
├── config/                    # 設定管理（Pydantic）
│   ├── __init__.py
│   └── models.py
├── utils/                     # ユーティリティ機能
│   ├── __init__.py
│   ├── retry.py              # APIリトライ（exponential backoff）
│   ├── notification.py       # エラー通知（Slack等）
│   └── rounding.py           # 数量・価格の丸め処理
├── schemas/                   # スキーマバリデーション
│   ├── __init__.py
│   └── validators.py
├── data_sources/              # データソース抽象化
│   ├── __init__.py
│   ├── base.py               # BaseDataSource ABC
│   ├── parquet.py            # Parquet実装
│   └── mock.py               # モック（テスト用）
├── calculators/               # 計算ロジック
│   ├── signals/
│   │   ├── __init__.py
│   │   └── base.py           # BaseSignalCalculator ABC
│   └── returns/
│       ├── __init__.py
│       ├── base.py           # BaseReturnCalculator ABC
│       └── log_return.py     # 対数リターン（デフォルト）
├── portfolio_constructors/    # ポートフォリオ構築
│   ├── __init__.py
│   ├── base.py               # BasePortfolioConstructor ABC
│   └── top_n.py              # TopN構築（デフォルト）
├── entry_order_creators/      # エントリー注文生成
│   ├── __init__.py
│   ├── base.py               # BaseEntryOrderCreator ABC
│   └── equal_weight.py       # 等ウェイト（デフォルト）
├── exit_order_creators/       # エグジット注文生成
│   ├── __init__.py
│   ├── base.py               # BaseExitOrderCreator ABC
│   └── full_exit.py          # 全決済（デフォルト）
├── exchange_clients/          # 執行クライアント
│   ├── __init__.py
│   ├── base.py               # BaseExchangeClient ABC
│   └── mock.py               # モック（バックテスト用）
├── io/                        # IOレイヤー抽象化
│   ├── __init__.py
│   ├── base.py               # BaseIO ABC
│   ├── local.py              # ローカルファイルシステム
│   └── s3.py                 # S3ストレージ
├── stores/                    # コンテキスト永続化
│   ├── __init__.py
│   ├── context_store.py      # ContextStore（単一実装）
│   └── in_memory.py          # InMemoryStore（テスト用）
├── models/                    # データモデル
│   ├── __init__.py
│   └── context.py            # Context Pydanticモデル
├── core/                      # コアエンジン
│   ├── __init__.py
│   ├── strategy_engine.py    # StrategyEngine（単一実装）
│   └── backtest_runner.py    # BacktestRunner（ループ管理）
├── metrics/                   # パフォーマンス指標計算
│   ├── __init__.py
│   └── calculator.py
├── analysis/                  # シグナル分析
│   ├── __init__.py
│   ├── rank_correlation.py
│   └── visualizer.py
├── diagnostics/               # バックテスト・実運用差異分析
│   ├── __init__.py
│   ├── comparison.py
│   └── visualizer.py
└── examples/                  # 実装例
    ├── __init__.py
    ├── signals/
    │   ├── __init__.py
    │   └── moving_average.py
    └── exchange_clients/
        ├── __init__.py
        └── exchange_api.py
```

## ドキュメント

詳細なドキュメントは `specs/001-qeel-core/` 配下にあります：

- [spec.md](specs/001-qeel-core/spec.md): 機能仕様書
- [plan.md](specs/001-qeel-core/plan.md): 実装計画
- [data-model.md](specs/001-qeel-core/data-model.md): データモデル定義
- [quickstart.md](specs/001-qeel-core/quickstart.md): クイックスタートガイド
- [research.md](specs/001-qeel-core/research.md): 設計研究
- [contracts/](specs/001-qeel-core/contracts/): ABCインターフェース仕様

## ライセンス

本プロジェクトは Apache License, Version 2.0 の下で公開されています。  
詳細は同梱の `LICENSE` ファイルをご確認ください。

## 著作権表示

Copyright 2025 tonic3561

## サポート

質問や問題がある場合は、GitHubのIssuesセクションで報告してください。
