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
2. `BaseReturnCalculator`: `calculate(market_data: pl.DataFrame) -> pl.DataFrame`
3. `BaseDataSource`: `fetch(start: datetime, end: datetime, symbols: list[str]) -> pl.DataFrame`
4. `BaseExecutor`: `submit_orders(orders: pl.DataFrame) -> None` / `fetch_fills() -> pl.DataFrame`
5. `BaseContextStore`: `save(context: Context) -> None` / `load() -> Context`

**Design Principle**:
- 各ABCは単一責任（SRP）に従う
- Pydanticモデルでパラメータとスキーマを定義
- docstringで日本語の詳細説明を記載

---

### 3. toml設定ファイルのバリデーション戦略

**Decision**: Pydantic `BaseSettings` またはカスタムモデルで設定を定義し、tomliで読み込み後即座にバリデーション

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
source_path = "/data/ohlcv.parquet"

[[data_sources]]
name = "earnings"
datetime_column = "announcement_date"
offset_seconds = 57600  # 決算発表は16時以降に利用可能（16時間 = 16*3600秒）
window_seconds = 7776000  # 90日 = 90*24*3600秒
source_type = "parquet"
source_path = "/data/earnings.parquet"

# コスト設定
[costs]
commission_rate = 0.001  # 手数料率（0.1%）
slippage_bps = 5  # スリッページ（5bps）
market_impact_model = "sqrt"  # "fixed" または "sqrt"
market_impact_coef = 0.0001

# 各メソッドの実行タイミング（ループ日付からのオフセット）
[timing]
calculate_signals = "09:00:00"  # シグナル計算タイミング
select_symbols = "09:05:00"
create_orders = "09:10:00"
submit_orders = "09:30:00"  # 執行タイミング

# コンテキスト保存設定
[context_store]
type = "local_json"  # "local_json", "local_parquet", "s3"
base_path = "/tmp/qeel_context"

# 実運用時のS3設定例（オプション）
# [context_store.s3]
# bucket = "my-trading-bucket"
# prefix = "qeel/context/"
# region = "ap-northeast-1"
```

---

### 4. iterationループの状態管理とコンテキスト永続化

**Decision**:
- `Context` をPydanticモデルで定義
- iteration終了時にJSON/Parquetで保存
- 次iteration開始時にロード

**Rationale**:
- Pydanticモデル → dict → JSON/Parquetは標準的なシリアライゼーションパターン
- Polars DataFrameは `write_parquet` / `read_parquet` でゼロコピー永続化可能
- バックテスト時はローカル、実運用時はS3/DBへの切り替えは `BaseContextStore` で抽象化

**Context Structure**:
```python
class Context(BaseModel):
    current_datetime: datetime  # 必須、iteration開始時に設定
    signals: pl.DataFrame | None  # SignalSchema準拠
    portfolio_plan: pl.DataFrame | None  # PortfolioSchema準拠
    orders: pl.DataFrame | None  # OrderSchema準拠
    current_positions: pl.DataFrame | None  # PositionSchema準拠
```

**Storage Abstraction**:
- `LocalStore(BaseContextStore)`: `Path` ベース、JSON/Parquet両対応（バックテスト用）
- `S3Store(BaseContextStore)`: boto3使用、JSON/Parquet両対応（**実運用必須対応、標準実装として提供**）

**Alternatives Considered**:
- **pickle**: セキュリティリスク、バージョン依存性
- **SQLiteインメモリ**: オーバーヘッド、Polarsとの親和性低い

---

### 5. バックテストと実運用の再現性保証

**Decision**:
- `BacktestEngine` と `LiveEngine` を共通の `BaseEngine` から継承
- シグナル計算〜執行条件計算は共通ロジック
- 実行部分（`submit_orders`, `fetch_fills`）のみ差し替え

**Rationale**:
- Template Methodパターンで共通フローを親クラスで定義
- サブクラスで `_execute_orders()` を実装（Backtestはモック、Liveは実API）
- 同一日時・同一データでiterationを実行すれば、生成されるOrdersが一致することを保証

**Key Design**:
```python
class BaseEngine(ABC):
    def run_iteration(self, date: datetime):
        data = self.fetch_data(date)
        signals = self.calculator.calculate(data)
        symbols = self.select_symbols(signals)
        orders = self.create_orders(signals, symbols)
        self._execute_orders(orders)  # サブクラスで実装

    @abstractmethod
    def _execute_orders(self, orders: pl.DataFrame):
        ...

class BacktestEngine(BaseEngine):
    def _execute_orders(self, orders: pl.DataFrame):
        # モック約定をシミュレート
        fills = simulate_fills(orders, self.config.costs)
        self.fills_history.append(fills)

class LiveEngine(BaseEngine):
    def _execute_orders(self, orders: pl.DataFrame):
        # 取引所APIに送信
        self.executor.submit_orders(orders)
```

**Testing Strategy**:
- 同一入力（date, data, context）で両Engineを実行
- `create_orders()` の出力を比較（assert DataFrameが一致）
- 数量・価格の丸めは `LiveExecutor` 内で実施（Backtestでは省略）

**Alternatives Considered**:
- **完全に別実装**: コード重複、再現性保証が困難
- **フラグでモード切り替え**: if文の氾濫、可読性低下

---

### 6. テスタビリティのためのDependency Injection

**Decision**: コンストラクタでABCインスタンスを注入

**Rationale**:
- pytest-mockでモックを注入しやすい
- テストで実データソース不要（`MockDataSource` を渡す）
- ユーザが独自実装を差し込める

**Example**:
```python
class BacktestEngine:
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
def test_backtest_run():
    mock_calculator = MockSignalCalculator()
    mock_data = MockDataSource()
    engine = BacktestEngine(
        calculator=mock_calculator,
        data_sources={"ohlcv": mock_data},
        context_store=InMemoryStore(),
        config=test_config,
    )
    engine.run_iteration(datetime(2023, 1, 1))
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

## 次のステップ

Phase 1で以下を設計：
- data-model.md: すべてのPydanticモデルとPolarsスキーマ定義
- contracts/: ユーザが実装すべきABCのインターフェース仕様
- quickstart.md: ユーザが最小構成でバックテストを実行する手順
