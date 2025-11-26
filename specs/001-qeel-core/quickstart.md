# Quickstart: Qeel バックテストライブラリ

**Date**: 2025-11-26
**Context**: ユーザが最小構成でバックテストを実行するためのクイックスタートガイド

## 前提条件

- Python 3.11+
- Qeelパッケージがインストール済み（`pip install qeel` または `uv add qeel`）

## 最小構成の例

### 1. プロジェクト構成

```text
my_backtest/
├── config.toml          # 設定ファイル
├── data/
│   └── ohlcv.csv        # 市場データ（OHLCV）
├── my_signal.py         # ユーザ定義シグナル計算クラス
└── run_backtest.py      # バックテスト実行スクリプト
```

### 2. 設定ファイル（config.toml）

```toml
[loop]
frequency = "1d"
start_date = "2023-01-01T00:00:00"
end_date = "2023-12-31T23:59:59"

[[data_sources]]
name = "ohlcv"
datetime_column = "datetime"
offset_hours = 0
window_days = 30
source_type = "csv"
source_path = "data/ohlcv.csv"

[costs]
commission_rate = 0.001  # 0.1%
slippage_bps = 5.0       # 5 bps
market_impact_model = "fixed"
market_impact_param = 0.0
```

### 3. データファイル（data/ohlcv.csv）

```csv
datetime,symbol,open,high,low,close,volume
2023-01-01 00:00:00,AAPL,150.0,152.0,149.0,151.0,1000000
2023-01-01 00:00:00,MSFT,250.0,252.0,249.0,251.0,800000
2023-01-02 00:00:00,AAPL,151.0,153.0,150.0,152.0,1100000
2023-01-02 00:00:00,MSFT,251.0,253.0,250.0,252.0,850000
...
```

### 4. シグナル計算クラス（my_signal.py）

```python
from pydantic import BaseModel, Field
import polars as pl
from qeel.calculators import BaseSignalCalculator
from qeel.schemas import SignalSchema

class MovingAverageCrossParams(BaseModel):
    """移動平均クロス戦略のパラメータ"""
    short_window: int = Field(default=5, gt=0)
    long_window: int = Field(default=20, gt=0)

class MovingAverageCrossCalculator(BaseSignalCalculator):
    """移動平均クロス戦略のシグナル計算

    短期移動平均 > 長期移動平均 の場合、正のシグナル
    短期移動平均 < 長期移動平均 の場合、負のシグナル
    """

    def calculate(self, data_sources: dict[str, pl.DataFrame]) -> pl.DataFrame:
        # OHLCVデータ取得
        ohlcv = data_sources["ohlcv"]

        # 移動平均計算
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

### 5. バックテスト実行スクリプト（run_backtest.py）

```python
from pathlib import Path
from qeel.config import Config
from qeel.data_sources import CSVDataSource
from qeel.executors import MockExecutor
from qeel.stores import LocalJSONStore
from qeel.engines import BacktestEngine
from my_signal import MovingAverageCrossCalculator, MovingAverageCrossParams

def main():
    # 設定読み込み
    config = Config.from_toml(Path("config.toml"))

    # シグナル計算クラスのインスタンス化
    signal_params = MovingAverageCrossParams(short_window=5, long_window=20)
    calculator = MovingAverageCrossCalculator(params=signal_params)

    # データソースのセットアップ
    data_sources = {}
    for ds_config in config.data_sources:
        if ds_config.source_type == "csv":
            data_sources[ds_config.name] = CSVDataSource(ds_config)
        # 他のソースタイプも同様に追加可能

    # 執行クラス（バックテストではモック）
    executor = MockExecutor(config.costs)

    # コンテキストストア
    context_store = LocalJSONStore(Path("context.json"))

    # バックテストエンジン構築
    engine = BacktestEngine(
        calculator=calculator,
        data_sources=data_sources,
        executor=executor,
        context_store=context_store,
        config=config,
    )

    # バックテスト実行
    print("バックテスト開始...")
    results = engine.run()

    # 結果表示
    print("\n=== バックテスト結果 ===")
    print(results.metrics)

    # 結果をファイルに保存
    results.metrics.write_csv("backtest_metrics.csv")
    results.fills.write_parquet("backtest_fills.parquet")

    print("\n結果を保存しました:")
    print("- backtest_metrics.csv")
    print("- backtest_fills.parquet")

if __name__ == "__main__":
    main()
```

### 6. 実行

```bash
python run_backtest.py
```

### 出力例

```text
バックテスト開始...
Iteration: 2023-01-01 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 365/365
バックテスト完了

=== バックテスト結果 ===
shape: (365, 6)
┌────────────┬──────────────┬────────────────────┬────────────┬──────────────┬──────────────┐
│ date       │ daily_return │ cumulative_return  │ volatility │ sharpe_ratio │ max_drawdown │
│ ---        │ ---          │ ---                │ ---        │ ---          │ ---          │
│ date       │ f64          │ f64                │ f64        │ f64          │ f64          │
╞════════════╪══════════════╪════════════════════╪════════════╪══════════════╪══════════════╡
│ 2023-01-01 │ 0.001        │ 0.001              │ 0.015      │ 0.067        │ 0.0          │
│ 2023-01-02 │ 0.002        │ 0.003              │ 0.015      │ 0.133        │ 0.0          │
│ ...        │ ...          │ ...                │ ...        │ ...          │ ...          │
└────────────┴──────────────┴────────────────────┴────────────┴──────────────┴──────────────┘

結果を保存しました:
- backtest_metrics.csv
- backtest_fills.parquet
```

## カスタマイズポイント

### 銘柄選定ロジックの追加

`BacktestEngine` にカスタム銘柄選定関数を渡すことで、シグナルから銘柄を選定できます：

```python
def select_top_symbols(signals: pl.DataFrame, top_n: int = 10) -> list[str]:
    """シグナルが大きい上位N銘柄を選定"""
    return (
        signals
        .sort("signal", descending=True)
        .head(top_n)
        ["symbol"]
        .to_list()
    )

engine = BacktestEngine(
    calculator=calculator,
    data_sources=data_sources,
    executor=executor,
    context_store=context_store,
    config=config,
    symbol_selector=select_top_symbols,  # カスタム選定関数
)
```

### 注文生成ロジックの追加

```python
def create_equal_weight_orders(
    signals: pl.DataFrame,
    selected_symbols: list[str],
    positions: pl.DataFrame,
    capital: float = 1_000_000.0,
) -> pl.DataFrame:
    """均等ウェイトで注文を生成"""
    n_symbols = len(selected_symbols)
    target_value_per_symbol = capital / n_symbols

    orders = []
    for symbol in selected_symbols:
        signal_row = signals.filter(pl.col("symbol") == symbol).row(0, named=True)
        signal_value = signal_row["signal"]

        # シグナルが正なら買い、負なら売り
        side = "buy" if signal_value > 0 else "sell"
        # 現在価格で数量計算（簡略化）
        quantity = abs(target_value_per_symbol / signal_row.get("close", 100.0))

        orders.append({
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": None,  # 成行
            "order_type": "market",
        })

    return pl.DataFrame(orders)

engine = BacktestEngine(
    calculator=calculator,
    data_sources=data_sources,
    executor=executor,
    context_store=context_store,
    config=config,
    order_creator=create_equal_weight_orders,  # カスタム注文生成関数
)
```

## 実運用への転用

バックテストと同じシグナル計算クラスを使用し、`LiveEngine` に切り替えることで実運用に転用できます：

```python
from qeel.engines import LiveEngine
from qeel.executors import ExchangeAPIExecutor  # ユーザ実装
from qeel.stores import S3Store  # ユーザ実装

# 実運用用の執行クラス
executor = ExchangeAPIExecutor(api_client=my_api_client)

# 実運用用のコンテキストストア
context_store = S3Store(bucket="my-bucket", key_prefix="qeel/context")

# 実運用エンジン
live_engine = LiveEngine(
    calculator=calculator,  # バックテストと同じクラス
    data_sources=live_data_sources,
    executor=executor,
    context_store=context_store,
    config=config,
)

# 当日を指定して単一iteration実行
from datetime import datetime
live_engine.run_iteration(datetime.now())
```

## 次のステップ

- [data-model.md](./data-model.md): データモデルの詳細
- [contracts/](./contracts/): ABCインターフェース仕様
- [research.md](./research.md): 設計の背景と選択理由
