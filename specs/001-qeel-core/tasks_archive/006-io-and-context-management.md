# Tasks: 006-io-and-context-management

**Input**: Design documents from `/specs/001-qeel-core/`
**Prerequisites**: plan.md (required), contracts/base_io.md (required), contracts/context_store.md (required), data-model.md (required)

**Branch**: `006-io-and-context-management`
**目的**: IOレイヤーとコンテキスト管理

**成果物**:
- `qeel/models/context.py` - Context Pydanticモデル
- `qeel/io/base.py` - BaseIO ABC
- `qeel/io/local.py` - LocalIO実装
- `qeel/io/s3.py` - S3IO実装
- `qeel/stores/context_store.py` - ContextStore（単一実装、IOレイヤー依存）
- `qeel/stores/in_memory.py` - InMemoryStore（テスト用）

**Tests**: TDDを厳守。Red-Green-Refactorサイクル必須（constitution準拠）

**依存ブランチ**: `002-core-config-and-schemas`（完了済み）

**Note**:
- contracts/base_io.mdおよびcontracts/context_store.mdの仕様に準拠して実装
- data-model.md 2.7（Context）を参照（2.9はcontracts/base_io.mdを正規仕様とする）
- S3IOのテストはmoto/boto3モックを使用
- ContextStore.load()はBaseExchangeClientを引数に取るが、007で実装予定のためモックで代用
- BaseExchangeClientの型注釈は`TYPE_CHECKING`ブロックでimportし、Forward Reference（文字列型注釈）を使用してimportエラーを回避

---

## Phase 19: IO and Context Package Setup

**Purpose**: IOパッケージとコンテキスト管理パッケージの初期化

- [x] T077 src/qeel/io/__init__.pyを作成（パッケージ初期化）
- [x] T078 [P] src/qeel/models/__init__.pyを作成（パッケージ初期化）
- [x] T079 [P] src/qeel/stores/__init__.pyを作成（パッケージ初期化）

**Checkpoint**: パッケージ構造完成

---

## Phase 20: Context Pydanticモデル

**Purpose**: Contextモデルの実装（data-model.md 2.7参照）

### Tests (TDD: RED)

- [x] T080 tests/unit/test_context.pyを作成
  - `test_context_requires_current_datetime`: current_datetimeは必須
  - `test_context_optional_fields_default_none`: signals, portfolio_plan, entry_orders, exit_orders, current_positionsはデフォルトNone
  - `test_context_accepts_polars_dataframe`: Polars DataFrameを保持可能
  - `test_context_serialization_arbitrary_types`: arbitrary_types_allowed設定が有効
  - `test_context_model_dump_excludes_dataframes`: model_dump()はDataFrameをシリアライズ不可（arbitrary_types_allowedの制限確認）

### Implementation (TDD: GREEN)

- [x] T081 src/qeel/models/context.pyにContextを実装（data-model.md 2.7参照）
  - `current_datetime: datetime`（必須）
  - `signals: pl.DataFrame | None`
  - `portfolio_plan: pl.DataFrame | None`
  - `entry_orders: pl.DataFrame | None`
  - `exit_orders: pl.DataFrame | None`
  - `current_positions: pl.DataFrame | None`

**Checkpoint**: `uv run pytest tests/unit/test_context.py` 全件パス

---

## Phase 21: BaseIO ABC

**Purpose**: IOレイヤー抽象基底クラスの実装（contracts/base_io.md参照）

### Tests (TDD: RED)

- [x] T082 tests/unit/test_io.pyを作成
  - `test_base_io_cannot_instantiate`: ABCは直接インスタンス化不可
  - `test_from_config_returns_local_io`: storage_type="local"でLocalIOを返す
  - `test_from_config_returns_s3_io`: storage_type="s3"でS3IOを返す
  - `test_from_config_raises_on_unsupported_storage`: サポートされていないstorage_typeでValueError
  - `test_from_config_raises_s3_missing_bucket`: s3でbucket未設定時にValueError
  - `test_from_config_raises_s3_missing_region`: s3でregion未設定時にValueError

### Implementation (TDD: GREEN)

- [x] T083 src/qeel/io/base.pyにBaseIO ABCを実装（contracts/base_io.md参照）
  - `from_config(cls, general_config: GeneralConfig) -> BaseIO`: ファクトリメソッド
  - `get_base_path(self, subdir: str) -> str`: 抽象メソッド
  - `get_partition_dir(self, base_path: str, target_datetime: datetime) -> str`: 抽象メソッド
  - `save(self, path: str, data: dict | pl.DataFrame, format: str) -> None`: 抽象メソッド
  - `load(self, path: str, format: str) -> dict | pl.DataFrame | None`: 抽象メソッド
  - `exists(self, path: str) -> bool`: 抽象メソッド
  - `list_files(self, path: str, pattern: str | None = None) -> list[str]`: 抽象メソッド

**Checkpoint**: `uv run pytest tests/unit/test_io.py -k "base"` 全件パス

---

## Phase 22: LocalIO実装

**Purpose**: ローカルファイルシステムIO実装（contracts/base_io.md参照）

### Tests (TDD: RED)

- [x] T084 tests/unit/test_io.pyにテストを追加
  - `test_local_io_get_base_path_returns_workspace_subdir`: ワークスペース配下のパスを返す
  - `test_local_io_get_partition_dir_creates_directory`: 年月パーティションディレクトリを作成して返す
  - `test_local_io_save_json`: dict形式でJSONファイルに保存
  - `test_local_io_save_parquet`: DataFrame形式でParquetファイルに保存
  - `test_local_io_save_raises_unsupported_format`: サポートされていないフォーマットでValueError
  - `test_local_io_save_parquet_raises_invalid_data`: parquetでdict指定時にValueError
  - `test_local_io_load_json`: JSONファイルからdictを読み込み
  - `test_local_io_load_parquet`: ParquetファイルからDataFrameを読み込み
  - `test_local_io_load_returns_none_when_not_exists`: ファイルが存在しない場合None
  - `test_local_io_load_raises_unsupported_format`: サポートされていないフォーマットでValueError
  - `test_local_io_exists_returns_true`: ファイルが存在する場合True
  - `test_local_io_exists_returns_false`: ファイルが存在しない場合False
  - `test_local_io_list_files_returns_all`: 指定パス配下の全ファイルを返す
  - `test_local_io_list_files_with_pattern`: パターン指定でフィルタリング
  - `test_local_io_list_files_returns_empty_when_not_exists`: 存在しないパスで空リスト

### Implementation (TDD: GREEN)

- [x] T085 src/qeel/io/local.pyにLocalIOを実装（contracts/base_io.md参照）
  - BaseIOを継承
  - get_workspace()を使用してベースパス取得
  - JSON/Parquet形式のsave/load
  - fnmatchによるパターンフィルタリング

**Checkpoint**: `uv run pytest tests/unit/test_io.py -k "local"` 全件パス

---

## Phase 23: S3IO実装

**Purpose**: S3ストレージIO実装（contracts/base_io.md参照）

**Prerequisites**: pyproject.tomlにboto3, moto依存関係を追加済みであること

- [x] T086-pre pyproject.tomlにboto3, moto依存関係を追加（S3テスト用）

### Tests (TDD: RED)

- [x] T086 tests/unit/test_io.pyにテストを追加（motoを使用）
  - `test_s3_io_get_base_path_returns_prefix`: S3キープレフィックスを返す
  - `test_s3_io_get_partition_dir_returns_prefix`: 年月パーティションプレフィックスを返す
  - `test_s3_io_save_json`: dict形式でS3にJSON保存
  - `test_s3_io_save_parquet`: DataFrame形式でS3にParquet保存
  - `test_s3_io_save_raises_unsupported_format`: サポートされていないフォーマットでValueError
  - `test_s3_io_load_json`: S3からJSONを読み込み
  - `test_s3_io_load_parquet`: S3からParquetを読み込み
  - `test_s3_io_load_returns_none_when_not_exists`: キーが存在しない場合None
  - `test_s3_io_exists_returns_true`: オブジェクトが存在する場合True
  - `test_s3_io_exists_returns_false`: オブジェクトが存在しない場合False
  - `test_s3_io_list_files_returns_all`: 指定プレフィックス配下の全オブジェクトを返す
  - `test_s3_io_list_files_with_pattern`: パターン指定でフィルタリング

### Implementation (TDD: GREEN)

- [x] T087 src/qeel/io/s3.pyにS3IOを実装（contracts/base_io.md参照）
  - BaseIOを継承
  - boto3クライアントを使用
  - BytesIO経由でParquet読み書き
  - paginatorによるlist_objects_v2

**Checkpoint**: `uv run pytest tests/unit/test_io.py -k "s3"` 全件パス

---

## Phase 24: InMemoryIO実装（テスト用）

**Purpose**: テスト用インメモリIO実装（contracts/base_io.md参照）

### Tests (TDD: RED)

- [x] T088 tests/unit/test_io.pyにテストを追加
  - `test_in_memory_io_save_and_load_json`: dict形式で保存・読み込み
  - `test_in_memory_io_save_and_load_dataframe`: DataFrame形式で保存・読み込み
  - `test_in_memory_io_exists`: 存在確認
  - `test_in_memory_io_list_files`: ファイル一覧取得

### Implementation (TDD: GREEN)

- [x] T089 src/qeel/io/in_memory.pyにInMemoryIOを実装（contracts/base_io.md参照）
  - BaseIOを継承
  - 内部dictにデータを保持
  - テスト用のシンプルな実装

**Checkpoint**: `uv run pytest tests/unit/test_io.py -k "memory"` 全件パス

---

## Phase 25: ContextStore実装

**Purpose**: コンテキスト永続化クラスの実装（contracts/context_store.md参照）

### Tests (TDD: RED)

- [x] T090 tests/unit/test_context_store.pyを作成
  - `test_context_store_save_signals`: シグナルを日付パーティショニングで保存
  - `test_context_store_save_portfolio_plan`: ポートフォリオ計画を保存
  - `test_context_store_save_entry_orders`: エントリー注文を保存
  - `test_context_store_save_exit_orders`: エグジット注文を保存
  - `test_context_store_load_returns_context`: 指定日付のコンテキストを復元
  - `test_context_store_load_returns_none_when_not_exists`: 保存された要素がない場合None
  - `test_context_store_load_partial_elements`: 一部の要素のみ存在する場合も正常に復元
  - `test_context_store_load_latest_returns_most_recent`: 最新日付のコンテキストを復元
  - `test_context_store_load_latest_returns_none_when_empty`: 保存データがない場合None
  - `test_context_store_exists_returns_true`: コンテキストが存在する場合True
  - `test_context_store_exists_returns_false`: コンテキストが存在しない場合False
  - `test_context_store_partition_directory_format`: 年月パーティション形式（YYYY/MM/）の確認

### Implementation (TDD: GREEN)

- [x] T091 src/qeel/stores/context_store.pyにContextStoreを実装（contracts/context_store.md参照）
  - `__init__(self, io: BaseIO)`
  - `save_signals(self, target_datetime: datetime, signals: pl.DataFrame) -> None`
  - `save_portfolio_plan(self, target_datetime: datetime, portfolio_plan: pl.DataFrame) -> None`
  - `save_entry_orders(self, target_datetime: datetime, entry_orders: pl.DataFrame) -> None`
  - `save_exit_orders(self, target_datetime: datetime, exit_orders: pl.DataFrame) -> None`
  - `load(self, target_datetime: datetime, exchange_client) -> Context | None`
  - `load_latest(self, exchange_client) -> Context | None`
  - `exists(self, target_datetime: datetime) -> bool`
  - `_find_latest_datetime(self) -> datetime | None`

**Checkpoint**: `uv run pytest tests/unit/test_context_store.py` 全件パス

---

## Phase 26: InMemoryStore実装（テスト用）

**Purpose**: テスト用インメモリストア実装（contracts/context_store.md参照）

### Tests (TDD: RED)

- [x] T092 tests/unit/test_context_store.pyにテストを追加
  - `test_in_memory_store_save_and_load`: 最新コンテキストのみ保持
  - `test_in_memory_store_overwrites_previous`: 上書き動作の確認
  - `test_in_memory_store_load_latest`: load_latestが最新を返す
  - `test_in_memory_store_exists`: 存在確認

### Implementation (TDD: GREEN)

- [x] T093 src/qeel/stores/in_memory.pyにInMemoryStoreを実装（contracts/context_store.md参照）
  - ContextStoreと同じインターフェース
  - 最新のコンテキストのみ保持
  - パーティショニングなし

**Checkpoint**: `uv run pytest tests/unit/test_context_store.py -k "memory"` 全件パス

---

## Phase 27: IO and Stores Module Exports and Integration

**Purpose**: モジュールエクスポートと統合テスト

### Tests (TDD: RED)

- [x] T094 tests/integration/test_io_integration.pyを作成
  - `test_local_io_with_config`: GeneralConfig(storage_type="local")からLocalIOを取得し、save/load/list_filesが正常動作
  - `test_context_store_with_local_io`: LocalIOを使用したContextStoreの動作確認
  - `test_context_store_partition_workflow`: 複数日付の保存・読み込みワークフロー

### Implementation (TDD: GREEN)

- [x] T095 src/qeel/io/__init__.pyにBaseIO, LocalIO, S3IO, InMemoryIOをエクスポート
- [x] T096 src/qeel/models/__init__.pyにContextをエクスポート
- [x] T097 src/qeel/stores/__init__.pyにContextStore, InMemoryStoreをエクスポート
- [x] T098 src/qeel/__init__.pyにio, models, storesモジュールを追加

**Checkpoint**: `uv run pytest tests/integration/test_io_integration.py` 全件パス

---

## Phase 28: Quality Assurance for 006

**Purpose**: 品質チェックと最終確認

- [x] T099 `uv run mypy src/qeel/io/` で型エラーゼロを確認
- [x] T100 [P] `uv run mypy src/qeel/models/` で型エラーゼロを確認
- [x] T101 [P] `uv run mypy src/qeel/stores/` で型エラーゼロを確認
- [x] T102 `uv run ruff check src/qeel/io/ src/qeel/models/ src/qeel/stores/` でリンターエラーゼロを確認
- [x] T103 `uv run ruff format src/qeel/io/ src/qeel/models/ src/qeel/stores/` でフォーマット適用
- [x] T104 `uv run pytest` で全テストパスを確認（002, 004, 005のテストも含む）

---

## Dependencies & Execution Order (006)

### Phase Dependencies

- **Phase 19 (Package Setup)**: 005完了後 - 即開始可能
- **Phase 20 (Context Model)**: Phase 19完了後
- **Phase 21 (BaseIO ABC)**: Phase 19完了後（Phase 20と並列可能）
- **Phase 22 (LocalIO)**: Phase 21完了後
- **Phase 23 (S3IO)**: Phase 21完了後（Phase 22と並列可能）
- **Phase 24 (InMemoryIO)**: Phase 21完了後（Phase 22, 23と並列可能）
- **Phase 25 (ContextStore)**: Phase 20, 21, 22完了後（LocalIOまたはInMemoryIOが必要）
- **Phase 26 (InMemoryStore)**: Phase 20完了後（ContextStoreと並列可能）
- **Phase 27 (Integration)**: Phase 22, 23, 24, 25, 26完了後
- **Phase 28 (QA)**: Phase 27完了後

### Execution Flow

```
005-calculator-abc (完了)
            |
            v
       Phase 19 (Setup)
            |
     ┌──────┴──────┐
     v             v
Phase 20       Phase 21
(Context)      (BaseIO ABC)
     |             |
     |      ┌──────┼──────┐
     |      v      v      v
     |   Phase   Phase   Phase
     |    22      23      24
     |  (Local) (S3IO) (Memory)
     |      |      |      |
     |      └──────┴──────┘
     |             |
     └─────┬───────┘
           |
     ┌─────┴─────┐
     v           v
  Phase 25   Phase 26
(ContextStore) (InMemoryStore)
     |           |
     └─────┬─────┘
           |
           v
       Phase 27 (Integration)
           |
           v
       Phase 28 (QA)
```

### Within Each Phase

- テストを先に作成し、失敗を確認（RED）
- 実装してテストをパス（GREEN）
- 必要に応じてリファクタリング（REFACTOR）

---

## Task Summary (006)

- **Total Tasks (006)**: 29 (T077-T105)
- **Setup Tasks**: 3
- **Context Model Tasks**: 2 (tests + impl)
- **BaseIO ABC Tasks**: 2 (tests + impl)
- **LocalIO Tasks**: 2 (tests + impl)
- **S3IO Tasks**: 2 (tests + impl)
- **InMemoryIO Tasks**: 2 (tests + impl)
- **ContextStore Tasks**: 2 (tests + impl)
- **InMemoryStore Tasks**: 2 (tests + impl)
- **Integration Tasks**: 5 (tests + impl)
- **QA Tasks**: 7

**Parallel Opportunities**:
- Phase 19内のT078, T079は並列実行可能
- Phase 20とPhase 21は並列実行可能
- Phase 22, 23, 24は並列実行可能
- Phase 25とPhase 26は並列実行可能
- Phase 28内のT100, T101は並列実行可能

---

## Implementation Strategy (006)

### MVP (最小実装)

1. Phase 19: Package Setup完了
2. Phase 20: Context Model完了
3. Phase 21: BaseIO ABC完了
4. Phase 22: LocalIO完了
5. Phase 24: InMemoryIO完了（テスト用）
6. Phase 25: ContextStore完了
7. Phase 28: QA実行

この時点でローカル環境でのコンテキスト永続化が動作し、後続ブランチ（007以降）の開発が可能

### Full Implementation

1. MVP完了後
2. Phase 23: S3IO完了（実運用対応）
3. Phase 26: InMemoryStore完了（テスト用ストア）
4. Phase 27: Integration完了
5. Phase 28: 最終QA

---

## Notes (006)

- contracts/base_io.mdおよびcontracts/context_store.mdの仕様に厳密に準拠
- data-model.md 2.7（Context）および2.9（IO Models）を参照
- ContextStore.load()はBaseExchangeClient引数を取るが、007で実装予定のためテストではモックを使用
- S3IOのテストはmoto（AWS SDK モック）を使用して実施
- 日本語コメント・docstring必須（constitution準拠）
- 各フェーズ完了後に品質ゲートチェック（mypy, ruff, pytest）
- BaseDataSource（004）、BaseSignalCalculator（005）と同様のパターンを踏襲
