# Quickstart: Qeel バックテストライブラリ

**Date**: 2025-11-26
**Context**: ユーザが最小構成でバックテストを実行するためのクイックスタートガイド

## 前提条件

- Python 3.11+

## 最小構成の例

### 1. インストール

Qeelパッケージをインストールします。

**pipを使用する場合:**

```bash
pip install qeel
```

**uvを使用する場合:**

```bash
uv add qeel
```

### 2. ワークスペースの初期化

`qeel init`でワークスペース構造と設定テンプレートを自動生成します。

#### ワークスペースディレクトリの指定

ワークスペースディレクトリは環境変数`QEEL_WORKSPACE`で指定できます。未設定の場合は、カレントディレクトリがワークスペースとして使用されます。

**方法1: カレントディレクトリを使用（環境変数未設定）**

```bash
mkdir my_backtest
cd my_backtest
qeel init
```

**方法2: 環境変数で明示的に指定**

```bash
export QEEL_WORKSPACE=/path/to/my_backtest
qeel init
```

#### 生成される構造

いずれの方法でも、以下の構造が生成されます：

```text
$QEEL_WORKSPACE/  (または カレントディレクトリ)
├── configs/
│   └── config.toml      # 設定ファイル（テンプレート）
├── inputs/              # 市場データ配置先
└── outputs/             # バックテスト結果出力先
```

### 3. プロジェクト構成

以下のファイルを追加します：

```text
$QEEL_WORKSPACE/
├── configs/
│   └── config.toml      # 設定ファイル（編集）
├── inputs/
│   └── ohlcv.parquet    # 市場データ（OHLCV、Parquet形式）
├── my_signal.py         # ユーザ定義シグナル計算クラス
└── run_backtest.py      # バックテスト実行スクリプト
```

### 4. 設定ファイル（configs/config.toml）

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
window_seconds = 2592000  # 30日 = 30 * 24 * 3600秒
source_type = "parquet"
source_path = "ohlcv.parquet"  # inputs/からの相対パス

# コスト設定
[costs]
commission_rate = 0.001  # 0.1%
slippage_bps = 5.0       # 5 bps
market_impact_model = "fixed"
market_impact_param = 0.0
```

### 5. データファイル（inputs/ohlcv.parquet）

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
df.write_parquet("inputs/ohlcv.parquet")
```

### 6. シグナル計算クラス（my_signal.py）

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

### 7. バックテスト実行スクリプト（run_backtest.py）

```python
from pathlib import Path

from my_signal import MovingAverageCrossCalculator, MovingAverageCrossParams

from qeel.config import Config
from qeel.data_sources.parquet import ParquetDataSource
from qeel.engines.backtest import BacktestEngine
from qeel.exchange_clients.mock import MockExchangeClient
from qeel.io.base import BaseIO
from qeel.order_creators.equal_weight import EqualWeightOrderCreator, EqualWeightParams
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

    # ポートフォリオ構築クラスのインスタンス化（デフォルト実装）
    constructor_params = TopNConstructorParams(top_n=10)
    portfolio_constructor = TopNPortfolioConstructor(params=constructor_params)

    # 注文生成クラスのインスタンス化（デフォルト実装）
    order_creator_params = EqualWeightParams(capital=1_000_000.0)
    order_creator = EqualWeightOrderCreator(params=order_creator_params)

    # データソースのセットアップ
    data_sources = {}
    for ds_config in config.data_sources:
        if ds_config.source_type == "parquet":
            data_sources[ds_config.name] = ParquetDataSource(ds_config, io)
        # カスタムソースタイプも追加可能

    # 執行クラス（バックテストではモック）
    exchange_client = MockExchangeClient(config.costs)

    # コンテキストストア
    context_store = ContextStore(io)

    # バックテストエンジン構築
    engine = BacktestEngine(
        calculator=calculator,
        portfolio_constructor=portfolio_constructor,
        order_creator=order_creator,
        data_sources=data_sources,
        exchange_client=exchange_client,
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

### 8. 実行

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

### ポートフォリオ構築ロジックのカスタマイズ

`BasePortfolioConstructor` を継承してカスタムポートフォリオ構築ロジックを実装できます：

```python
from pydantic import BaseModel, Field
import polars as pl
from qeel.portfolio_constructors import BasePortfolioConstructor

class CustomConstructorParams(BaseModel):
    """カスタムポートフォリオ構築のパラメータ"""
    top_n: int = Field(default=10, gt=0, description="選定する銘柄数")
    min_signal_threshold: float = Field(default=0.0, description="最小シグナル閾値")

class CustomPortfolioConstructor(BasePortfolioConstructor):
    """シグナル上位N銘柄かつ閾値以上のものでポートフォリオを構築し、メタデータ付きで返す"""

    def construct(self, signals: pl.DataFrame, current_positions: pl.DataFrame) -> pl.DataFrame:
        """
        Args:
            signals: シグナルDataFrame（SignalSchema準拠）
            current_positions: 現在のポジション（PositionSchema準拠）

        Returns:
            構築済みポートフォリオDataFrame（PortfolioSchema準拠、メタデータ含む）
        """
        from qeel.schemas import SignalSchema, PositionSchema, PortfolioSchema

        SignalSchema.validate(signals)
        PositionSchema.validate(current_positions)

        # 閾値フィルタ + 上位N選定 + メタデータ付与
        portfolio = (
            signals
            .filter(pl.col("signal") >= self.params.min_signal_threshold)
            .sort("signal", descending=True)
            .head(self.params.top_n)
            .select(["datetime", "symbol", "signal"])
            .rename({"signal": "signal_strength"})
        )

        return PortfolioSchema.validate(portfolio)

# 使用例
constructor_params = CustomConstructorParams(top_n=10, min_signal_threshold=0.5)
portfolio_constructor = CustomPortfolioConstructor(params=constructor_params)

engine = BacktestEngine(
    calculator=calculator,
    data_sources=data_sources,
    exchange_client=exchange_client,
    context_store=context_store,
    config=config,
    portfolio_constructor=portfolio_constructor,  # カスタムコンストラクタ
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
        portfolio_plan: pl.DataFrame,
        current_positions: pl.DataFrame,
        ohlcv: pl.DataFrame,
    ) -> pl.DataFrame:
        """
        Args:
            portfolio_plan: 構築済みポートフォリオDataFrame（メタデータ含む）
            current_positions: 現在のポジション
            ohlcv: OHLCV価格データ

        Returns:
            注文DataFrame（OrderSchema準拠）
        """
        from qeel.schemas import PortfolioSchema

        PortfolioSchema.validate(portfolio_plan)

        orders = []
        max_value_per_symbol = self.params.capital * self.params.max_position_pct

        for row in portfolio_plan.iter_rows(named=True):
            symbol = row["symbol"]

            # メタデータからシグナル強度を取得
            signal_value = row.get("signal_strength", 0.0)

            # 現在価格取得
            price_row = ohlcv.filter(pl.col("symbol") == symbol)
            if price_row.height == 0:
                continue
            current_price = price_row["close"][0]

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
    exchange_client=exchange_client,
    context_store=context_store,
    config=config,
    order_creator=order_creator,  # カスタム注文生成
)
```

## 実運用への転用

バックテストと同じシグナル計算クラスを使用し、`LiveEngine` に切り替えることで実運用に転用できます：

```python
from datetime import datetime

from qeel.engines.live import LiveEngine
from qeel.exchange_clients.examples.exchange_api import ExchangeAPIClient  # ユーザ実装
from qeel.io.base import BaseIO
from qeel.order_creators.equal_weight import EqualWeightOrderCreator, EqualWeightParams
from qeel.portfolio_constructors.top_n import TopNPortfolioConstructor, TopNConstructorParams
from qeel.stores.context_store import ContextStore

# 実運用用設定（storage_type="s3"）
# config.tomlの[general]セクションで設定:
# storage_type = "s3"
# s3_bucket = "my-bucket"
# s3_region = "ap-northeast-1"

# IOレイヤーのセットアップ（S3を使用）
io = BaseIO.from_config(config.general)

# ポートフォリオ構築クラスのインスタンス化（バックテストと同じ）
constructor_params = TopNConstructorParams(top_n=10)
portfolio_constructor = TopNPortfolioConstructor(params=constructor_params)

# 注文生成クラスのインスタンス化（バックテストと同じ）
order_creator_params = EqualWeightParams(capital=1_000_000.0)
order_creator = EqualWeightOrderCreator(params=order_creator_params)

# 実運用用の執行クラス
exchange_client = ExchangeAPIClient(api_client=my_api_client)

# 実運用用のコンテキストストア（S3経由）
context_store = ContextStore(io)

# 実運用エンジン
live_engine = LiveEngine(
    calculator=calculator,  # バックテストと同じクラス
    portfolio_constructor=portfolio_constructor,  # バックテストと同じクラス
    order_creator=order_creator,  # バックテストと同じクラス
    data_sources=live_data_sources,
    exchange_client=exchange_client,
    context_store=context_store,
    config=config,
)

# 当日を指定して単一iteration実行
live_engine.run_iteration(datetime.now())
```

## 次のステップ

- [data-model.md](./data-model.md): データモデルの詳細
- [contracts/](./contracts/): ABCインターフェース仕様
- [research.md](./research.md): 設計の背景と選択理由
