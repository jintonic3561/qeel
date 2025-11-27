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
│   └── ohlcv.parquet    # 市場データ（OHLCV、Parquet形式）
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
offset_seconds = 0
window_seconds = 2592000  # 30日 = 30 * 24 * 3600秒
source_type = "parquet"
source_path = "data/ohlcv.parquet"

[costs]
commission_rate = 0.001  # 0.1%
slippage_bps = 5.0       # 5 bps
market_impact_model = "fixed"
market_impact_param = 0.0
```

### 3. データファイル（data/ohlcv.parquet）

Parquet形式のファイルを用意します。Parquetは型情報を保持し、高速・圧縮効率が良いフォーマットです。

PythonでParquetファイルを作成する例：

```python
import polars as pl
from datetime import datetime

# サンプルデータ
data = {
    "datetime": [
        datetime(2023, 1, 1, 0, 0, 0),
        datetime(2023, 1, 1, 0, 0, 0),
        datetime(2023, 1, 2, 0, 0, 0),
        datetime(2023, 1, 2, 0, 0, 0),
    ],
    "symbol": ["AAPL", "MSFT", "AAPL", "MSFT"],
    "open": [150.0, 250.0, 151.0, 251.0],
    "high": [152.0, 252.0, 153.0, 253.0],
    "low": [149.0, 249.0, 150.0, 250.0],
    "close": [151.0, 251.0, 152.0, 252.0],
    "volume": [1000000, 800000, 1100000, 850000],
}

df = pl.DataFrame(data)
df.write_parquet("data/ohlcv.parquet")
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
from qeel.data_sources import ParquetDataSource
from qeel.executors import MockExecutor
from qeel.stores import LocalStore
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
        if ds_config.source_type == "parquet":
            data_sources[ds_config.name] = ParquetDataSource(ds_config)
        # カスタムソースタイプも追加可能

    # 執行クラス（バックテストではモック）
    executor = MockExecutor(config.costs)

    # コンテキストストア（JSON形式）
    context_store = LocalStore(Path("context.json"), format="json")

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

### 銘柄選定ロジックのカスタマイズ

`BaseSymbolSelector` を継承してカスタム銘柄選定ロジックを実装できます：

```python
from pydantic import BaseModel, Field
import polars as pl
from qeel.selectors import BaseSymbolSelector

class CustomSelectorParams(BaseModel):
    """カスタム銘柄選定のパラメータ"""
    top_n: int = Field(default=10, gt=0, description="選定する銘柄数")
    min_signal_threshold: float = Field(default=0.0, description="最小シグナル閾値")

class CustomSymbolSelector(BaseSymbolSelector):
    """シグナル上位N銘柄かつ閾値以上のものを選定"""

    def select(self, signals: pl.DataFrame, positions: pl.DataFrame) -> list[str]:
        """
        Args:
            signals: シグナルDataFrame（SignalSchema準拠）
            positions: 現在のポジション（PositionSchema準拠）

        Returns:
            選定された銘柄リスト
        """
        from qeel.schemas import SignalSchema, PositionSchema

        SignalSchema.validate(signals)
        PositionSchema.validate(positions)

        return (
            signals
            .filter(pl.col("signal") >= self.params.min_signal_threshold)
            .sort("signal", descending=True)
            .head(self.params.top_n)
            ["symbol"]
            .to_list()
        )

# 使用例
selector_params = CustomSelectorParams(top_n=10, min_signal_threshold=0.5)
symbol_selector = CustomSymbolSelector(params=selector_params)

engine = BacktestEngine(
    calculator=calculator,
    data_sources=data_sources,
    executor=executor,
    context_store=context_store,
    config=config,
    symbol_selector=symbol_selector,  # カスタムセレクタ
)
```

### 注文生成ロジックのカスタマイズ

```python
from qeel.order_creators import BaseOrderCreator
from qeel.schemas import OrderSchema

class CustomOrderCreatorParams(BaseModel):
    """カスタム注文生成のパラメータ"""
    capital: float = Field(default=1_000_000.0, gt=0.0, description="運用資金")
    max_position_pct: float = Field(default=0.2, gt=0.0, le=1.0, description="1銘柄の最大ポジション比率")

class RiskParityOrderCreator(BaseOrderCreator):
    """リスクパリティに基づいて注文を生成"""

    def create(
        self,
        signals: pl.DataFrame,
        selected_symbols: list[str],
        positions: pl.DataFrame,
        market_data: pl.DataFrame,
    ) -> pl.DataFrame:
        """
        Args:
            signals: シグナルDataFrame
            selected_symbols: 選定された銘柄リスト
            positions: 現在のポジション
            market_data: 市場データ（価格情報）

        Returns:
            注文DataFrame（OrderSchema準拠）
        """
        orders = []
        max_value_per_symbol = self.params.capital * self.params.max_position_pct

        for symbol in selected_symbols:
            signal_row = signals.filter(pl.col("symbol") == symbol).row(0, named=True)
            signal_value = signal_row["signal"]

            # 現在価格取得
            price_row = market_data.filter(pl.col("symbol") == symbol).row(0, named=True)
            current_price = price_row["close"]

            # シグナルの強さに応じて数量計算
            target_value = max_value_per_symbol * abs(signal_value)
            quantity = target_value / current_price

            side = "buy" if signal_value > 0 else "sell"

            orders.append({
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": None,  # 成行
                "order_type": "market",
            })

        return OrderSchema.validate(pl.DataFrame(orders))

# 使用例
order_creator_params = CustomOrderCreatorParams(capital=1_000_000.0, max_position_pct=0.15)
order_creator = RiskParityOrderCreator(params=order_creator_params)

engine = BacktestEngine(
    calculator=calculator,
    data_sources=data_sources,
    executor=executor,
    context_store=context_store,
    config=config,
    order_creator=order_creator,  # カスタム注文生成
)
```

## 実運用への転用

バックテストと同じシグナル計算クラスを使用し、`LiveEngine` に切り替えることで実運用に転用できます：

```python
from qeel.engines import LiveEngine
from qeel.executors import ExchangeAPIExecutor  # ユーザ実装
from qeel.stores import S3Store

# 実運用用の執行クラス
executor = ExchangeAPIExecutor(api_client=my_api_client)

# 実運用用のコンテキストストア（JSON形式）
context_store = S3Store(bucket="my-bucket", key_prefix="qeel/context", format="json")

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
