# Implementation Branch Status

実装ブランチの進捗一覧。完了済みタスクの詳細は `tasks_archive.md` を参照。

## Phase 1: Core Infrastructure（基盤構築）

- [x] **002-core-config-and-schemas** - 設定管理とスキーマバリデーションの基盤 (T001-T045)
- [x] **004-data-source-abc** - データソースABCと共通ヘルパーメソッド (T046-T057)
- [x] **005-calculator-abc** - シグナル計算ABCとサンプル実装 (T058-T076)
- [x] **006-io-and-context-management** - IOレイヤーとコンテキスト管理 (T077-T104)
- [ ] **007-exchange-client-and-mock** - 取引所クライアントABCとモック約定・ポジション管理 (T105-T116)

## Phase 2: Core Engine（P1対応）

- [ ] **008-portfolio-and-orders** - ポートフォリオ構築・注文生成のABCとデフォルト実装
- [ ] **009-strategy-engine** - StrategyEngine実装（ステップ単位実行）
- [ ] **010-backtest-runner** - BacktestRunner実装（ループ管理）
- [ ] **011-metrics-calculation** - パフォーマンス指標計算

## Phase 3: Production Examples（P2対応）

- [ ] **012-executor-examples** - 実運用用Executor実装例とデプロイメントドキュメント

## Phase 4 & 5: Signal Analysis / Backtest-Live Divergence（P3対応）

- [ ] **013-return-calculator-abc** - リターン計算ABCとデフォルト実装
- [ ] **014-signal-analysis** - シグナル分析機能
- [ ] **015-backtest-live-divergence** - バックテストと実運用の差異検証

---

# Tasks: 007-prerequisites（007ブランチ前提条件修正）

**Input**: Design documents from `/specs/001-qeel-core/`
**Prerequisites**: 006ブランチ完了、設計ドキュメント更新済み

**Branch**: `007-exchange-client-and-mock`（前提条件修正フェーズ）
**目的**: 設計ドキュメント更新に伴う既存実装の整合性修正

**成果物**:
- `CostConfig.market_fill_price_type`フィールド追加
- `LocalIO.load()`のglobパターン対応
- `S3IO.load()`のPolarsネイティブS3読み込み対応
- `ParquetDataSource`標準実装の新規作成

**Tests**: TDDを厳守。Red-Green-Refactorサイクル必須（constitution準拠）

---

## Phase 1: CostConfig拡張（market_fill_price_type追加）

**Purpose**: MockExchangeClientの成行注文約定ロジックで使用するフィールドを追加

### Tests (TDD: RED)

- [ ] T105 tests/unit/test_config.pyに以下のテストを追加:
  - `test_cost_config_market_fill_price_type_default`: デフォルト値が"next_open"であることを確認
  - `test_cost_config_market_fill_price_type_current_close`: "current_close"でバリデーションパス
  - `test_cost_config_market_fill_price_type_invalid`: 不正な値でValidationError

### Implementation (TDD: GREEN)

- [ ] T106 src/qeel/config/models.pyのCostConfigに`market_fill_price_type`フィールドを追加
  - デフォルト値: "next_open"
  - バリデータ: {"next_open", "current_close"}のいずれかを許可
  - data-model.md 1.2に準拠

**Checkpoint**: `uv run pytest tests/unit/test_config.py -k market_fill_price_type` 全件パス

---

## Phase 2: BaseIO.load()のglobパターン対応

**Purpose**: ParquetDataSourceがglobパターン（`*.parquet`等）を使用できるようにする

### Tests (TDD: RED)

- [ ] T107 tests/unit/test_io.pyに以下のテストを追加:
  - `test_local_io_is_glob_pattern_asterisk`: "*"を含むパスでTrueを返す
  - `test_local_io_is_glob_pattern_question`: "?"を含むパスでTrueを返す
  - `test_local_io_is_glob_pattern_bracket`: "["を含むパスでTrueを返す
  - `test_local_io_is_glob_pattern_normal`: globパターンを含まないパスでFalseを返す
  - `test_local_io_load_parquet_glob_pattern`: globパターンでPolarsに直接委譲される（存在チェックスキップ）

### Implementation (TDD: GREEN)

- [ ] T108 src/qeel/io/local.pyに`_is_glob_pattern()`メソッドを追加
  - "*", "?", "["のいずれかを含む場合Trueを返す
- [ ] T109 src/qeel/io/local.pyの`load()`メソッドを修正
  - parquet形式かつglobパターンの場合、存在チェックをスキップ
  - Polarsの`read_parquet()`に直接委譲（contracts/base_io.md準拠）

**Checkpoint**: `uv run pytest tests/unit/test_io.py -k glob` 全件パス

---

## Phase 3: S3IO.load()のPolarsネイティブS3対応

**Purpose**: S3上のParquetファイルをPolarsのネイティブS3サポートで読み込む

### Tests (TDD: RED)

- [ ] T110 tests/unit/test_io.pyに以下のテストを追加（モックboto3使用）:
  - `test_s3_io_storage_options_initialized`: `_storage_options`が正しく初期化される
  - `test_s3_io_to_s3_uri`: `_to_s3_uri()`が正しいURI形式を返す
  - `test_s3_io_load_parquet_uses_native_s3`: parquet形式でPolarsネイティブS3読み込みを使用（モック確認）

### Implementation (TDD: GREEN)

- [ ] T111 src/qeel/io/s3.pyの`__init__()`に`_storage_options`を追加
  - `{"aws_region": region}`形式
- [ ] T112 src/qeel/io/s3.pyに`_to_s3_uri()`メソッドを追加
  - `f"s3://{self.bucket}/{path}"`形式でURIを返す
- [ ] T113 src/qeel/io/s3.pyの`load()`メソッドを修正
  - parquet形式の場合、`pl.read_parquet(s3_uri, storage_options=self._storage_options)`を使用
  - contracts/base_io.md準拠

**Checkpoint**: `uv run pytest tests/unit/test_io.py -k s3` 全件パス（モック環境）

---

## Phase 4: ParquetDataSource標準実装

**Purpose**: quickstart.mdで参照されているParquetDataSource標準実装を提供

### Tests (TDD: RED)

- [ ] T114 tests/unit/test_data_sources.pyにTestParquetDataSourceクラスを追加:
  - `test_parquet_data_source_fetch_returns_dataframe`: fetch()がDataFrameを返す
  - `test_parquet_data_source_uses_io_layer`: IOレイヤー経由でデータを読み込む
  - `test_parquet_data_source_applies_helpers`: ヘルパーメソッド（_normalize_datetime_column等）を適用
  - `test_parquet_data_source_raises_on_missing`: データが存在しない場合ValueErrorをraise

### Implementation (TDD: GREEN)

- [ ] T115 src/qeel/data_sources/parquet.pyを新規作成
  - `ParquetDataSource`クラスを実装
  - contracts/base_data_source.mdの実装例に準拠
  - IOレイヤー経由でParquetファイルを読み込み
  - 共通ヘルパーメソッドを使用した前処理

- [ ] T116 src/qeel/data_sources/__init__.pyに`ParquetDataSource`をエクスポート

### Integration Test

- [ ] T117 tests/integration/test_data_source_integration.pyにParquetDataSource統合テストを追加:
  - `test_parquet_data_source_with_local_io`: LocalIOと連携してParquetを読み込み
  - `test_parquet_data_source_with_glob_pattern`: globパターンでの読み込み確認

**Checkpoint**: `uv run pytest tests/ -k parquet` 全件パス

---

## Phase 5: 品質ゲート確認

- [ ] T118 `uv run mypy src/qeel/` 型エラーゼロ
- [ ] T119 `uv run ruff check src/qeel/` リンターエラーゼロ
- [ ] T120 `uv run pytest tests/` 全テストパス

**Final Checkpoint**: 007ブランチ前提条件修正完了、007本体実装に進行可能

---

## Dependencies

```
T105 → T106 (CostConfig拡張)
     ↓
T107 → T108 → T109 (LocalIO glob対応)
     ↓
T110 → T111 → T112 → T113 (S3IO ネイティブS3対応)
     ↓
T114 → T115 → T116 → T117 (ParquetDataSource実装)
     ↓
T118, T119, T120 (品質ゲート) - 並列実行可能
```

## Parallel Execution Opportunities

- Phase 1とPhase 2は並列実行可能（異なるファイルを修正）
- Phase 4のT115とT116は並列実行可能
- Phase 5のT118, T119は並列実行可能

---

