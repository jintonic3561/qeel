# Research: Qeel - 量的トレーディング向けバックテストライブラリ

**Date**: 2025-11-26
**Context**: Phase 0 research for backtest library implementation

## 調査項目

### 1. Polars DataFrameベースの型安全なスキーマ管理

**Decision**: Pydantic v2のモデルバリデータを使用し、Polars DataFrameの列スキーマを実行時に検証する

**Rationale**:
- Pydantic v2は高速な実行時バリデーションを提供
- Polars自体は列の型を持つが、実行時の厳密なスキーマチェックは提供しない
- カスタムPydanticバリデータで、期待される列名・型・nullability を検証可能
- 例: `pl.DataFrame` → `validate_schema(df, expected_columns={"datetime": pl.Datetime, "symbol": pl.Utf8, "close": pl.Float64})`

**Alternatives Considered**:
- **pandera**: Polars対応が限定的、pandas中心の設計
- **手動チェック**: 可読性低下、バリデーションロジックの重複

**Implementation Note**:
- `qeel.schemas.validators` モジュールで共通バリデータを実装
- すべてのDataFrame入出力でバリデーションを強制
- エラーメッセージは日本語で、不足列・型不一致を明示

---

### 2. 抽象基底クラス（ABC）パターンの設計

**Decision**: `abc.ABC` と `abstractmethod` を使用し、ユーザ拡張ポイントを明示する

**Rationale**:
- Pythonの標準ライブラリ、追加依存なし
- インターフェース契約を型ヒントとdocstringで明確化
- サブクラスが抽象メソッドを実装しない場合、インスタンス化時にエラー

**Alternatives Considered**:
- **Protocol（typing.Protocol）**: ダックタイピング、契約の強制力が弱い
- **通常クラス + NotImplementedError**: 実行時まで検出できない

**Key ABCs**:
1. `BaseSignalCalculator`: `calculate(data_sources: dict[str, pl.DataFrame]) -> pl.DataFrame`
2. `BaseReturnCalculator`: `calculate(ohlcv: pl.DataFrame) -> pl.DataFrame`
3. `BaseDataSource`: `fetch(start: datetime, end: datetime, symbols: list[str]) -> pl.DataFrame`
4. `BaseExchangeClient`: `submit_orders(orders: pl.DataFrame) -> None` / `fetch_fills(start: datetime, end: datetime) -> pl.DataFrame`
5. `BaseContextStore`: `save(context: Context) -> None` / `load() -> Context`

**Design Principle**:
- 各ABCは単一責任（SRP）に従う
- Pydanticモデルでパラメータとスキーマを定義
- docstringで日本語の詳細説明を記載

---

### 3. toml設定ファイルのバリデーション戦略

**Decision**: Pydantic `BaseSettings` またはカスタムモデルで設定を定義し、tomllib（Python 3.11+標準ライブラリ）で読み込み後即座にバリデーション

**Rationale**:
- Pydanticのフィールドバリデーションで型チェック・必須項目・カスタムルール適用可能
- 起動時に一度だけバリデーション、エラー時は詳細メッセージで停止
- toml → dict → Pydanticモデル変換パターンは一般的

**Implementation**:
```python
# qeel/config/models.py
from pydantic import BaseModel, Field, field_validator
from pathlib import Path

class DataSourceConfig(BaseModel):
    name: str
    datetime_column: str
    offset_seconds: int = 0
    window_seconds: int
    source_path: Path

    @field_validator('source_path')
    def path_must_exist(cls, v):
        if not v.exists():
            raise ValueError(f"データソースパスが存在しません: {v}")
        return v

class Config(BaseModel):
    data_sources: list[DataSourceConfig]
    costs: CostConfig
    loop: LoopConfig
```

**Error Handling**:
- ValidationErrorを捕捉し、日本語で整形
- エラー箇所（section.field）を明示
- 期待される型・制約を表示

**Alternatives Considered**:
- **手動パース**: エラーメッセージの品質低下、保守困難
- **dynaconf等の設定ライブラリ**: 過剰な機能、型安全性が弱い

**Complete TOML Configuration Example**:

```toml
# config.toml - バックテスト設定ファイル例

# General設定
[general]
storage_type = "local"  # "local" または "s3"
# S3使用時は以下を指定
# s3_bucket = "my-qeel-bucket"
# s3_region = "ap-northeast-1"

# ループ管理設定
[loop]
start_date = "2020-01-01"
end_date = "2023-12-31"
frequency = "1D"  # 日足（"1H"=時間足、"1W"=週足）

# 取引日判定（オプション）
[loop.trading_calendar]
country = "JP"  # 日本の取引カレンダー
skip_holidays = true

# データソース定義（複数可）
[[data_sources]]
name = "ohlcv"
datetime_column = "timestamp"
offset_seconds = 0  # データが利用可能になる時刻オフセット（UTC基準、秒）
window_seconds = 2592000  # 各iterationで取得する過去データ（秒）、30日 = 30*24*3600
source_type = "parquet"
source_path = "inputs/ohlcv.parquet"  # ワークスペースからの相対パス

[[data_sources]]
name = "earnings"
datetime_column = "announcement_date"
offset_seconds = 57600  # 決算発表は16時以降に利用可能（16時間 = 16*3600秒）
window_seconds = 7776000  # 90日 = 90*24*3600秒
source_type = "parquet"
source_path = "inputs/earnings.parquet"  # ワークスペースからの相対パス

# コスト設定
[costs]
commission_rate = 0.001  # 手数料率（0.1%）
slippage_bps = 5  # スリッページ（5bps）
market_impact_model = "sqrt"  # "fixed" または "sqrt"
market_impact_coef = 0.0001

# 各ステップの実行タイミング（ループ日付からのオフセット、秒数で指定）
[loop.step_timings]
calculate_signals_offset_seconds = 32400    # 09:00:00 = 9 * 3600
construct_portfolio_offset_seconds = 32700  # 09:05:00
create_entry_orders_offset_seconds = 33000  # 09:10:00
create_exit_orders_offset_seconds = 33120   # 09:12:00
submit_entry_orders_offset_seconds = 34200  # 09:30:00
submit_exit_orders_offset_seconds = 34320   # 09:32:00
```

**Note**: ワークスペース構造は以下の通り:
```
$QEEL_WORKSPACE/  (未設定時はカレントディレクトリ)
├── configs/
│   └── config.toml
├── inputs/
│   ├── ohlcv.parquet
│   └── earnings.parquet
└── outputs/
    ├── context/  (iteration内の各ステップ出力を保存)
    └── reports/  (パフォーマンスレポート等)
```

`qeel init`コマンドで上記構造と設定テンプレートが自動生成される。

---

### 4. iterationループの状態管理とコンテキスト永続化

**Decision**:
- `Context` をPydanticモデルで定義
- iteration終了時にJSON/Parquetで保存
- 次iteration開始時にロード

**Rationale**:
- Pydanticモデル → dict → JSON/Parquetは標準的なシリアライゼーションパターン
- Polars DataFrameは `write_parquet` / `read_parquet` でゼロコピー永続化可能
- バックテスト時はローカル、実運用時はS3/DBへの切り替えは `BaseIO` で抽象化

**Context Structure**:
```python
class Context(BaseModel):
    current_datetime: datetime  # 必須、iteration開始時に設定
    signals: pl.DataFrame | None  # SignalSchema準拠
    portfolio_plan: pl.DataFrame | None  # PortfolioSchema準拠
    entry_orders: pl.DataFrame | None  # OrderSchema準拠
    exit_orders: pl.DataFrame | None  # OrderSchema準拠
    current_positions: pl.DataFrame | None  # PositionSchema準拠
```

**Alternatives Considered**:
- **pickle**: セキュリティリスク、バージョン依存性
- **SQLiteインメモリ**: オーバーヘッド、Polarsとの親和性低い

---

### 5. バックテストと実運用の再現性保証とステップ単位実行

**Decision**:
- `StrategyEngine`が各ステップを独立して実行可能なステップを提供
- `BacktestRunner`が`StrategyEngine`インスタンスを保持し、ループ管理とタイミング制御を担当
- 実運用時は外部スケジューラが`StrategyEngine.run_step`を直接呼び出し
- 各ステップ間でコンテキストを永続化し、状態を受け渡す

**Rationale**:
- **Composition over Inheritance**: 継承階層を排除し、責任分離を明確化（StrategyEngine: ステップ実行、BacktestRunner: ループ管理）
- **Serverless Support**: 各ステップを数時間空けて実行可能（Lambda等のサーバーレス環境で利用可能）
- **Reproducibility**: バックテストと実運用で同一の`StrategyEngine`を使用し、同一日時・同一データで同じOrdersを生成することを保証
- **Testability**: `StrategyEngine`を単独でテスト可能、モックを注入しやすい

**Key Design**:
```python
class StrategyEngine:
    """単一実装、ステップ単位実行を提供"""

    def run_step(self, date: datetime, step_name: str) -> None:
        """指定ステップのみ実行し、結果をContextStoreに保存"""
        context = self.context_store.load(date) or Context(current_datetime=date)

        if step_name == "calculate_signals":
            data = self._fetch_data(date)
            signals = self.calculator.calculate(data)
            self.context_store.save_signals(date, signals)

        elif step_name == "construct_portfolio":
            context = self.context_store.load(date)
            portfolio_plan = self.portfolio_constructor.construct(context.signals, context.current_positions)
            self.context_store.save_portfolio_plan(date, portfolio_plan)

        # ... 他のステップも同様

    def run_steps(self, date: datetime, step_names: list[str]) -> None:
        """複数ステップを逐次実行"""
        for step_name in step_names:
            self.run_step(date, step_name)

class BacktestRunner:
    """StrategyEngineを保持し、ループ管理のみを担当（継承なし）"""

    def __init__(self, engine: StrategyEngine, config: Config):
        self.engine = engine
        self.config = config

    def run(self, start_date: datetime, end_date: datetime) -> None:
        """全期間のバックテストを実行"""
        for date in self._date_range(start_date, end_date):
            if not self._is_trading_day(date):
                continue
            # 全ステップを実行
            self.engine.run_steps(date, [
                "calculate_signals",
                "construct_portfolio",
                "create_entry_orders",
                "create_exit_orders",
                "submit_entry_orders",
                "submit_exit_orders"
            ])
```

**Production Deployment**:
```python
# Lambda Handler（各ステップを独立したLambda関数にデプロイ）
def lambda_handler_calculate_signals(event, context):
    date = datetime.fromisoformat(event['date'])
    engine = StrategyEngine(calculator, portfolio_constructor, entry_order_creator, exit_order_creator, data_sources, exchange_client, context_store, config)
    engine.run_step(date, "calculate_signals")

def lambda_handler_submit_entry_orders(event, context):
    date = datetime.fromisoformat(event['date'])
    engine = StrategyEngine(calculator, portfolio_constructor, entry_order_creator, exit_order_creator, data_sources, exchange_client, context_store, config)
    engine.run_step(date, "submit_entry_orders")

def lambda_handler_submit_exit_orders(event, context):
    date = datetime.fromisoformat(event['date'])
    engine = StrategyEngine(calculator, portfolio_constructor, entry_order_creator, exit_order_creator, data_sources, exchange_client, context_store, config)
    engine.run_step(date, "submit_exit_orders")

# EventBridgeで各Lambdaをスケジュール
# 09:00 → calculate_signals
# 10:00 → construct_portfolio
# 14:00 → create_entry_orders
# 14:05 → create_exit_orders
# 15:00 → submit_entry_orders
# 15:05 → submit_exit_orders
```

**Testing Strategy**:
- 同一入力（date, data, context）で`StrategyEngine.run_step`を実行
- バックテストと実運用で`create_entry_orders()`, `create_exit_orders()`の出力を比較（assert DataFrameが一致）
- 数量・価格の丸めは`ExchangeClient`実装内で実施（MockExchangeClientでは省略、ExchangeAPIClientで実施）

**Alternatives Considered**:
- **BaseEngine + BacktestEngine/LiveEngine継承**: 継承階層が不要、実運用は単にStrategyEngineのステップ単位実行を使えばよい
- **全ステップを一括実行のみ**: サーバーレス環境で数時間稼働が必要、コスト高、柔軟性低い

---

### 6. テスタビリティのためのDependency Injection

**Decision**: コンストラクタでABCインスタンスを注入

**Rationale**:
- pytest-mockでモックを注入しやすい
- テストで実データソース不要（`MockDataSource` を渡す）
- ユーザが独自実装を差し込める

**Example**:
```python
class StrategyEngine:
    def __init__(
        self,
        calculator: BaseSignalCalculator,
        data_sources: dict[str, BaseDataSource],
        context_store: BaseContextStore,
        config: Config,
    ):
        self.calculator = calculator
        self.data_sources = data_sources
        self.context_store = context_store
        self.config = config
```

**Testing**:
```python
def test_strategy_engine_run_step():
    mock_calculator = MockSignalCalculator()
    mock_data = MockDataSource()
    engine = StrategyEngine(
        calculator=mock_calculator,
        data_sources={"ohlcv": mock_data},
        context_store=InMemoryStore(),
        config=test_config,
    )
    engine.run_step(datetime(2023, 1, 1), "calculate_signals")
    # アサーション
```

**Alternatives Considered**:
- **グローバルシングルトン**: テスト並列実行不可、状態共有
- **ファクトリパターン**: 過剰な抽象化

---

### 7. パフォーマンス指標計算のベストプラクティス

**Decision**:
- Polarsの `lazy` APIと `agg` を活用
- 日次リターン → 累積リターン → シャープレシオ等をチェーンで計算

**Rationale**:
- Polarsはクエリ最適化を自動実行
- メモリ効率的な大規模データ処理

**Example**:
```python
def calculate_metrics(fills: pl.DataFrame) -> pl.DataFrame:
    return (
        fills
        .lazy()
        .group_by("date")
        .agg([
            pl.col("pnl").sum().alias("daily_return"),
        ])
        .with_columns([
            pl.col("daily_return").cum_sum().alias("cumulative_return"),
            pl.col("daily_return").std().alias("volatility"),
        ])
        .with_columns([
            (pl.col("daily_return").mean() / pl.col("volatility")).alias("sharpe_ratio"),
        ])
        .collect()
    )
```

**Alternatives Considered**:
- **pandas**: 速度劣る、メモリ消費大
- **NumPy直接**: 可読性低下、Polarsのゼロコピー利点失う

---

### 8. ワークスペース管理とIOレイヤーの統一

**Decision**:
- 環境変数`QEEL_WORKSPACE`でワークスペースディレクトリを指定可能にする
- `qeel init`コマンドでワークスペース構造（configs/inputs/outputs）を自動生成
- IOレイヤー（BaseIO、LocalIO、S3IO）でLocal/S3の判別を一手に引き受ける
- ContextStoreとDataSourceは単一実装とし、IOレイヤー経由でデータ操作

**Rationale**:
- **DRY原則**: LocalStore/S3Storeの重複実装を排除。パーティショニングロジックをIOレイヤーに集約
- **Single Responsibility**: Local/S3判別をIOレイヤーに委譲し、ContextStore/DataSourceは永続化ロジックに専念
- **可読性**: ワークスペース構造が明確化され、設定の意図が理解しやすい
- **ユーザ体験**: `qeel init`で即座に利用可能な環境を構築できる

**Workspace Structure**:
```
$QEEL_WORKSPACE/  (未設定時はカレントディレクトリ)
├── configs/
│   └── config.toml  (General設定、データソース設定等)
├── inputs/
│   ├── ohlcv.parquet
│   └── earnings.parquet
└── outputs/
    ├── context/  (iteration内の各ステップ出力を保存、YYYY/MM/でパーティショニング)
    └── reports/  (パフォーマンスレポート等)
```

**IO Layer Design**:
- `BaseIO.from_config(general_config)`: ファクトリメソッドでGeneral設定から適切な実装を返す
- `LocalIO`: ワークスペース配下のファイルシステム操作
- `S3IO`: S3バケット配下のオブジェクト操作
- 共通メソッド:
  - `get_base_path(subdir)`: inputs/outputsのベースパス取得
  - `get_partition_dir(base_path, datetime)`: YYYY/MM/パーティショニング
  - `save(path, data, format)`: dict→JSON、DataFrame→Parquet
  - `load(path, format)`: JSON→dict、Parquet→DataFrame
  - `exists(path)`: ファイル存在確認

**Context Store Implementation**:
```python
class ContextStore:  # ABCではなく単一実装
    def __init__(self, io: BaseIO):
        self.io = io
        self.base_path = io.get_base_path("outputs/context")

    def save_signals(self, target_datetime: datetime, signals: pl.DataFrame) -> None:
        partition_dir = self.io.get_partition_dir(self.base_path, target_datetime)
        date_str = target_datetime.strftime("%Y-%m-%d")
        path = f"{partition_dir}/signals_{date_str}.parquet"
        self.io.save(path, signals, format="parquet")
```

**Data Source Implementation**:
```python
class ParquetDataSource(BaseDataSource):
    def __init__(self, config: DataSourceConfig, io: BaseIO):
        super().__init__(config)
        self.io = io

    def fetch(self, start: datetime, end: datetime, symbols: list[str]) -> pl.DataFrame:
        # IOレイヤー経由で読み込み
        base_path = self.io.get_base_path("inputs")
        df = self.io.load(f"{base_path}/{self.config.source_path}", format="parquet")
        # 以降は既存のフィルタリングロジック
        ...
```

**Alternatives Considered**:
- **LocalStore/S3Store分離**: パーティショニングロジックが重複し、DRY原則に違反
- **設定ファイルにbase_pathをハードコード**: 環境間での移植性が低下

**Benefits**:
- ContextStore、DataSourceから200行以上の重複コードを削減
- ストレージ切り替えはGeneral設定のみで完結（コード変更不要）
- テスト時はInMemoryIOを注入可能（ファイルシステム不要）

---

## 次のステップ

Phase 1で以下を設計：
- data-model.md: すべてのPydanticモデルとPolarsスキーマ定義
- contracts/: ユーザが実装すべきABCのインターフェース仕様
- quickstart.md: ユーザが最小構成でバックテストを実行する手順
