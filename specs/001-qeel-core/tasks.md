# Tasks: 002-core-config-and-schemas

**Input**: Design documents from `/specs/001-qeel-core/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md

**Branch**: `002-core-config-and-schemas`
**目的**: 設定管理とスキーマバリデーションの基盤

**成果物**:
- `qeel/config/` - Pydantic設定モデル（Config, DataSourceConfig, CostConfig, LoopConfig, StepTimingConfig, GeneralConfig）
- `qeel/schemas/` - DataFrameスキーマバリデータ（OHLCVSchema, SignalSchema等）
- `qeel/utils/workspace.py` - get_workspace()実装
- toml読み込み・バリデーション機能
- 型ヒント + mypy設定

**Tests**: TDDを厳守。Red-Green-Refactorサイクル必須（constitution準拠）

**Organization**: このブランチはUser Storyに直接紐付かない基盤実装であるため、機能単位でフェーズを構成

## Format: `[ID] [P?] Description`

- **[P]**: 並列実行可能（異なるファイル、依存関係なし）
- 各タスクにファイルパスを明記

---

## Phase 1: Setup (プロジェクト初期化)

**Purpose**: プロジェクト構造の確立とツールチェーンの設定

- [x] T001 pyproject.tomlにqeelパッケージ設定と依存関係を追加（pydantic, polars）
- [x] T002 mypy.iniをstrictモードで設定
- [x] T003 [P] ruff設定をpyproject.tomlに追加
- [x] T004 [P] pytest設定をpyproject.tomlに追加
- [x] T005 src/qeel/__init__.pyを作成（パッケージ初期化）
- [x] T006 [P] src/qeel/config/__init__.pyを作成
- [x] T007 [P] src/qeel/schemas/__init__.pyを作成
- [x] T008 [P] src/qeel/utils/__init__.pyを作成
- [x] T009 [P] tests/unit/__init__.pyを作成
- [x] T010 tests/conftest.pyを作成（pytest共通設定）

**Checkpoint**: プロジェクト構造完成、`uv run mypy src/` および `uv run ruff check src/` がパス

---

## Phase 2: Workspace Utilities

**Purpose**: ワークスペース管理機能の実装

### Tests (TDD: RED)

- [x] T011 tests/unit/test_workspace.pyを作成
  - `test_get_workspace_returns_cwd_when_env_not_set`: 環境変数未設定時にカレントディレクトリを返す
  - `test_get_workspace_returns_env_path_when_set`: 環境変数設定時にそのパスを返す
  - `test_get_workspace_raises_when_path_not_exists`: 存在しないパス指定時にValueErrorをraise

### Implementation (TDD: GREEN)

- [x] T012 src/qeel/utils/workspace.pyにget_workspace()を実装（data-model.md 1.5参照）

**Checkpoint**: `uv run pytest tests/unit/test_workspace.py` 全件パス

---

## Phase 3: Configuration Models

**Purpose**: Pydantic設定モデルの実装

### Tests (TDD: RED)

- [x] T013 tests/unit/test_config.pyを作成
  - `test_data_source_config_valid`: 正常な設定でバリデーションパス
  - `test_data_source_config_invalid_source_type`: 不正なsource_typeでValidationError
  - `test_cost_config_defaults`: デフォルト値の確認
  - `test_cost_config_invalid_market_impact_model`: 不正なmarket_impact_modelでValidationError
  - `test_step_timing_config_defaults`: デフォルト値の確認
  - `test_loop_config_frequency_parse_days`: "1d"をtimedeltaに変換
  - `test_loop_config_frequency_parse_hours`: "4h"をtimedeltaに変換
  - `test_loop_config_frequency_parse_weeks`: "1w"をtimedeltaに変換
  - `test_loop_config_frequency_parse_minutes`: "30m"をtimedeltaに変換
  - `test_loop_config_frequency_invalid_format`: 不正形式でValidationError
  - `test_loop_config_end_before_start`: end_date < start_dateでValidationError
  - `test_general_config_local_storage`: storage_type="local"で正常
  - `test_general_config_s3_storage_valid`: storage_type="s3"で必須項目ありで正常
  - `test_general_config_s3_missing_bucket`: s3でbucket未設定時にValidationError
  - `test_general_config_s3_missing_region`: s3でregion未設定時にValidationError

### Implementation (TDD: GREEN)

- [x] T014 [P] src/qeel/config/models.pyにDataSourceConfigを実装（data-model.md 1.1参照）
- [x] T015 [P] src/qeel/config/models.pyにCostConfigを実装（data-model.md 1.2参照）
- [x] T016 [P] src/qeel/config/models.pyにStepTimingConfigを実装（data-model.md 1.3参照）
- [x] T017 src/qeel/config/models.pyにLoopConfigを実装（data-model.md 1.3参照、frequencyパース含む）
- [x] T018 src/qeel/config/models.pyにGeneralConfigを実装（data-model.md 1.4参照）

**Checkpoint**: `uv run pytest tests/unit/test_config.py` 全件パス

---

## Phase 4: Config Root Model and TOML Loading

**Purpose**: 全体設定モデルとTOML読み込み機能

### Tests (TDD: RED)

- [x] T019 tests/unit/test_config.pyにテストを追加
  - `test_config_from_toml_valid`: 正常なTOMLファイルからConfig生成
  - `test_config_from_toml_missing_file`: ファイル不存在時にFileNotFoundError
  - `test_config_from_toml_invalid_toml`: 不正なTOML形式でエラー
  - `test_config_from_toml_validation_error`: バリデーションエラーでValidationError
  - `test_config_from_toml_default_path`: パス未指定時にワークスペース/configs/config.tomlを参照

### Implementation (TDD: GREEN)

- [x] T020 src/qeel/config/models.pyにConfigクラスを実装（data-model.md 1.6参照）
- [x] T021 tests/fixtures/にテスト用TOMLファイルを作成
  - `tests/fixtures/valid_config.toml` - 正常な設定
  - `tests/fixtures/invalid_config.toml` - バリデーションエラー用

**Checkpoint**: `uv run pytest tests/unit/test_config.py` 全件パス

---

## Phase 5: DataFrame Schema Validators

**Purpose**: Polars DataFrameのスキーマバリデータ実装

### Tests (TDD: RED)

- [x] T022 tests/unit/test_schemas.pyを作成
  - `test_ohlcv_schema_valid`: 正常なDataFrameでバリデーションパス
  - `test_ohlcv_schema_missing_column`: 必須列欠損でValueError
  - `test_ohlcv_schema_wrong_dtype`: 型不一致でValueError
  - `test_signal_schema_valid`: 正常なDataFrameでバリデーションパス
  - `test_signal_schema_allows_extra_columns`: 追加列は許容
  - `test_portfolio_schema_valid`: 正常なDataFrameでバリデーションパス
  - `test_position_schema_valid`: 正常なDataFrameでバリデーションパス
  - `test_order_schema_valid`: 正常なDataFrameでバリデーションパス
  - `test_order_schema_invalid_side`: 不正なside値でValueError
  - `test_order_schema_invalid_order_type`: 不正なorder_type値でValueError
  - `test_fill_report_schema_valid`: 正常なDataFrameでバリデーションパス
  - `test_metrics_schema_valid`: 正常なDataFrameでバリデーションパス

### Implementation (TDD: GREEN)

- [x] T023 [P] src/qeel/schemas/validators.pyにOHLCVSchemaを実装（data-model.md 2.1参照）
- [x] T024 [P] src/qeel/schemas/validators.pyにSignalSchemaを実装（data-model.md 2.2参照）
- [x] T025 [P] src/qeel/schemas/validators.pyにPortfolioSchemaを実装（data-model.md 2.3参照）
- [x] T026 [P] src/qeel/schemas/validators.pyにPositionSchemaを実装（data-model.md 2.4参照）
- [x] T027 src/qeel/schemas/validators.pyにOrderSchemaを実装（data-model.md 2.5参照、side/order_typeバリデーション）
- [x] T028 [P] src/qeel/schemas/validators.pyにFillReportSchemaを実装（data-model.md 2.6参照）
- [x] T029 [P] src/qeel/schemas/validators.pyにMetricsSchemaを実装（data-model.md 2.8参照）

**Checkpoint**: `uv run pytest tests/unit/test_schemas.py` 全件パス

---

## Phase 6: Parameter Models

**Purpose**: ユーザ定義パラメータの基底クラス実装

### Tests (TDD: RED)

- [x] T030 tests/unit/test_params.pyを作成
  - `test_signal_calculator_params_extensible`: 継承してカスタムパラメータ追加可能
  - `test_portfolio_constructor_params_extensible`: 継承してカスタムパラメータ追加可能
  - `test_entry_order_creator_params_extensible`: 継承してカスタムパラメータ追加可能
  - `test_exit_order_creator_params_extensible`: 継承してカスタムパラメータ追加可能
  - `test_return_calculator_params_extensible`: 継承してカスタムパラメータ追加可能

### Implementation (TDD: GREEN)

- [x] T031 [P] src/qeel/config/params.pyにSignalCalculatorParamsを実装（data-model.md 3.1参照）
- [x] T032 [P] src/qeel/config/params.pyにPortfolioConstructorParamsを実装（data-model.md 3.2参照）
- [x] T033 [P] src/qeel/config/params.pyにEntryOrderCreatorParamsを実装（data-model.md 3.3参照）
- [x] T034 [P] src/qeel/config/params.pyにExitOrderCreatorParamsを実装（data-model.md 3.4参照）
- [x] T035 [P] src/qeel/config/params.pyにReturnCalculatorParamsを実装（data-model.md 3.5参照）

**Checkpoint**: `uv run pytest tests/unit/test_params.py` 全件パス

---

## Phase 7: Module Exports and Integration

**Purpose**: モジュールエクスポートと統合テスト

### Tests (TDD: RED)

- [x] T036 tests/integration/test_config_integration.pyを作成
  - `test_full_config_load_from_toml`: 完全なTOMLからConfigロードし、全プロパティにアクセス可能
  - `test_workspace_and_config_integration`: get_workspace()とConfig.from_toml()の連携

### Implementation (TDD: GREEN)

- [x] T037 src/qeel/__init__.pyにpublic APIをエクスポート（Config, get_workspace等）
- [x] T038 src/qeel/config/__init__.pyに設定クラスをエクスポート
- [x] T039 src/qeel/schemas/__init__.pyにスキーマクラスをエクスポート
- [x] T040 src/qeel/utils/__init__.pyにユーティリティ関数をエクスポート

**Checkpoint**: `uv run pytest tests/integration/` 全件パス

---

## Phase 8: Quality Assurance (Polish)

**Purpose**: 品質チェックと最終確認

- [x] T041 `uv run mypy src/qeel/` で型エラーゼロを確認
- [x] T042 `uv run ruff check src/qeel/` でリンターエラーゼロを確認
- [x] T043 `uv run ruff format src/qeel/` でフォーマット適用
- [x] T044 `uv run pytest` で全テストパスを確認
- [x] T045 tests/fixtures/にresearch.mdの設定例を反映したサンプルTOMLを追加

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: 依存なし - 即開始可能
- **Phase 2 (Workspace)**: Phase 1完了後
- **Phase 3 (Config Models)**: Phase 2完了後（get_workspaceに依存）
- **Phase 4 (Config Root)**: Phase 3完了後
- **Phase 5 (Schemas)**: Phase 1完了後（Config非依存、並列可能）
- **Phase 6 (Params)**: Phase 1完了後（Config非依存、並列可能）
- **Phase 7 (Integration)**: Phase 4, 5, 6完了後
- **Phase 8 (QA)**: Phase 7完了後

### Parallel Opportunities

```
Phase 1 (Setup)
     |
     v
   ┌─┴─┬──────────┐
   v   v          v
Phase 2  Phase 5   Phase 6
   |     (Schemas) (Params)
   v        |        |
Phase 3     |        |
   |        |        |
   v        |        |
Phase 4     |        |
   |        |        |
   └────────┴────────┘
            |
            v
        Phase 7 (Integration)
            |
            v
        Phase 8 (QA)
```

### Within Each Phase

- テストを先に作成し、失敗を確認（RED）
- 実装してテストをパス（GREEN）
- 必要に応じてリファクタリング（REFACTOR）
- [P]マークのタスクは並列実行可能

---

## Task Summary

- **Total Tasks**: 45
- **Setup Tasks**: 10
- **Workspace Tasks**: 2
- **Config Model Tasks**: 6 (tests) + 5 (impl) = 11
- **Config Root Tasks**: 5 (tests) + 3 (impl) = 8
- **Schema Tasks**: 12 (tests) + 7 (impl) = 19... (adjusted)
- **Param Tasks**: 5 (tests) + 5 (impl) = 10
- **Integration Tasks**: 2 (tests) + 4 (impl) = 6
- **QA Tasks**: 5

**Parallel Opportunities**:
- Phase 5 (Schemas) と Phase 6 (Params) は Phase 2-4 と並列実行可能
- 各フェーズ内で [P] マークのタスクは並列実行可能

---

## Implementation Strategy

### MVP (最小実装)

1. Phase 1: Setup完了
2. Phase 2: Workspace完了
3. Phase 3-4: Config完了
4. Phase 8: QA実行

この時点で設定読み込み機能が動作し、後続ブランチ（003以降）の開発が可能

### Full Implementation

1. MVP完了後
2. Phase 5: Schemas完了（後続ブランチでデータバリデーションに使用）
3. Phase 6: Params完了（後続ブランチでABC実装に使用）
4. Phase 7: Integration完了
5. Phase 8: 最終QA

---

## Notes

- data-model.mdの各セクション番号を参照してタスクを実装
- 日本語コメント・docstring必須（constitution準拠）
- 各フェーズ完了後に品質ゲートチェック（mypy, ruff, pytest）
- 不明点はresearch.mdの設定例を参照

---

# Tasks: 004-data-source-abc

**Input**: Design documents from `/specs/001-qeel-core/`
**Prerequisites**: plan.md (required), contracts/base_data_source.md (required), data-model.md (required)

**Branch**: `004-data-source-abc`
**目的**: データソースABCと共通ヘルパーメソッド、テスト用実装

**成果物**:
- `qeel/data_sources/base.py` - BaseDataSource ABC
  - `_normalize_datetime_column()`: datetime列の正規化
  - `_adjust_window_for_offset()`: offset_secondsによるwindow調整（リーク防止）
  - `_filter_by_datetime_and_symbols()`: datetime範囲と銘柄でフィルタリング
- `qeel/data_sources/mock.py` - MockDataSource（テスト用）

**Tests**: TDDを厳守。Red-Green-Refactorサイクル必須（constitution準拠）

**依存ブランチ**: `002-core-config-and-schemas`（完了済み）

**Note**:
- MockDataSourceでは`BaseIO`を使用しない方針（IOレイヤーは006で実装予定）
- `BaseIO`はオプショナル引数として定義し、ユーザが任意で利用可能にする
- contracts/base_data_source.mdの仕様に準拠して実装

---

## Phase 9: Data Source Package Setup

**Purpose**: データソースパッケージの初期化

- [x] T046 src/qeel/data_sources/__init__.pyを作成（パッケージ初期化）

**Checkpoint**: パッケージ構造完成

---

## Phase 10: BaseDataSource ABC

**Purpose**: データソース抽象基底クラスの実装

**テスト方針**: ヘルパーメソッド（`_normalize_datetime_column`等）はprotectedメソッドだが、
ユーザがサブクラスで利用することを想定した公開APIの一部である。
テストでは具象サブクラス（テスト用スタブ）を作成し、ヘルパーメソッドを呼び出して検証する。

### Tests (TDD: RED)

- [x] T047 tests/unit/test_data_sources.pyを作成
  - `test_base_data_source_cannot_instantiate`: ABCは直接インスタンス化不可
  - `test_normalize_datetime_column_renames`: datetime_columnが"datetime"以外の場合リネームされる（テスト用スタブ経由）
  - `test_normalize_datetime_column_casts_to_datetime`: 型がDatetimeでない場合キャストされる
  - `test_normalize_datetime_column_already_datetime`: すでに"datetime"列の場合は変更なし
  - `test_normalize_datetime_column_missing_column`: 指定されたdatetime_columnがDataFrameに存在しない場合KeyErrorをraise
  - `test_adjust_window_for_offset_positive`: 正のoffset_secondsでwindowが過去方向に調整される
  - `test_adjust_window_for_offset_zero`: offset_seconds=0の場合windowは変化なし
  - `test_adjust_window_for_offset_negative`: 負のoffset_secondsでwindowが未来方向に調整される
  - `test_adjust_window_prevents_data_leak`: offset_seconds適用後のwindowでフィルタリングした場合、未来データが含まれないことを確認
  - `test_filter_by_datetime_and_symbols_filters_correctly`: datetime範囲とsymbolsで正しくフィルタリング
  - `test_filter_by_datetime_and_symbols_empty_result`: 条件に一致するデータがない場合は空DataFrame
  - `test_filter_by_datetime_and_symbols_empty_symbols`: symbols引数が空リストの場合、空DataFrameを返す

### Implementation (TDD: GREEN)

- [x] T048 src/qeel/data_sources/base.pyにBaseDataSource ABCを実装（contracts/base_data_source.md参照）
  - `__init__(self, config: DataSourceConfig, io: BaseIO | None = None)`: ioをオプショナルに
  - `fetch(self, start, end, symbols)`: 抽象メソッド
  - `_normalize_datetime_column(self, df)`: datetime列正規化ヘルパー
  - `_adjust_window_for_offset(self, start, end)`: window調整ヘルパー
  - `_filter_by_datetime_and_symbols(self, df, start, end, symbols)`: フィルタリングヘルパー

**Checkpoint**: `uv run pytest tests/unit/test_data_sources.py -k "base"` 全件パス

---

## Phase 11: MockDataSource

**Purpose**: テスト用モックデータソースの実装

### Tests (TDD: RED)

- [x] T049 tests/unit/test_data_sources.pyにテストを追加
  - `test_mock_data_source_returns_dataframe`: fetch()がPolars DataFrameを返す
  - `test_mock_data_source_respects_symbols`: 指定されたsymbolsのデータのみ返す
  - `test_mock_data_source_respects_datetime_range`: 指定されたdatetime範囲内のデータを返す
  - `test_mock_data_source_returns_empty_when_no_match`: 条件に一致するデータがない場合は空DataFrame
  - `test_mock_data_source_default_schema`: デフォルトで最小OHLCVスキーマを持つ（datetime, symbol, open, high, low, close, volume）

### Implementation (TDD: GREEN)

- [x] T050 src/qeel/data_sources/mock.pyにMockDataSourceを実装（contracts/base_data_source.md参照）
  - BaseDataSourceを継承
  - コンストラクタでモックデータを受け取る（または生成）
  - fetch()でフィルタリング済みDataFrameを返す
  - ヘルパーメソッドの使用例として参照可能な実装

**Checkpoint**: `uv run pytest tests/unit/test_data_sources.py -k "mock"` 全件パス

---

## Phase 12: Data Source Module Exports and Integration

**Purpose**: モジュールエクスポートと統合テスト

### Tests (TDD: RED)

- [x] T051 tests/integration/test_data_source_integration.pyを作成
  - `test_mock_data_source_with_config`: DataSourceConfigを使用してMockDataSourceを初期化し、fetch()が正常動作
  - `test_data_source_helper_chain`: ヘルパーメソッドを連鎖して使用した場合の動作確認

### Implementation (TDD: GREEN)

- [x] T052 src/qeel/data_sources/__init__.pyにBaseDataSource, MockDataSourceをエクスポート
- [x] T053 src/qeel/__init__.pyにdata_sourcesモジュールを追加（必要に応じて）

**Checkpoint**: `uv run pytest tests/integration/test_data_source_integration.py` 全件パス

---

## Phase 13: Quality Assurance for 004

**Purpose**: 品質チェックと最終確認

- [x] T054 `uv run mypy src/qeel/data_sources/` で型エラーゼロを確認
- [x] T055 `uv run ruff check src/qeel/data_sources/` でリンターエラーゼロを確認
- [x] T056 `uv run ruff format src/qeel/data_sources/` でフォーマット適用
- [x] T057 `uv run pytest` で全テストパスを確認（002のテストも含む）

---

## Dependencies & Execution Order (004)

### Phase Dependencies

- **Phase 9 (Package Setup)**: 002完了後 - 即開始可能
- **Phase 10 (BaseDataSource ABC)**: Phase 9完了後
- **Phase 11 (MockDataSource)**: Phase 10完了後
- **Phase 12 (Integration)**: Phase 11完了後
- **Phase 13 (QA)**: Phase 12完了後

### Execution Flow

```
002-core-config-and-schemas (完了)
            |
            v
       Phase 9 (Setup)
            |
            v
       Phase 10 (ABC)
            |
            v
       Phase 11 (Mock)
            |
            v
       Phase 12 (Integration)
            |
            v
       Phase 13 (QA)
```

### Within Each Phase

- テストを先に作成し、失敗を確認（RED）
- 実装してテストをパス（GREEN）
- 必要に応じてリファクタリング（REFACTOR）

---

## Task Summary (004)

- **Total Tasks (004)**: 12 (T046-T057)
- **Setup Tasks**: 1
- **ABC Tasks**: 2 (tests + impl)
- **Mock Tasks**: 2 (tests + impl)
- **Integration Tasks**: 3 (tests + impl)
- **QA Tasks**: 4

**Parallel Opportunities**:
- Phase 10内のテストケースは並列で作成可能
- Phase 11内のテストケースは並列で作成可能

---

## Implementation Strategy (004)

### MVP (最小実装)

1. Phase 9: Package Setup完了
2. Phase 10: BaseDataSource ABC完了
3. Phase 13: QA実行

この時点でABCが定義され、ユーザはカスタムデータソースを実装可能

### Full Implementation

1. MVP完了後
2. Phase 11: MockDataSource完了（テスト用実装）
3. Phase 12: Integration完了
4. Phase 13: 最終QA

---

## Notes (004)

- contracts/base_data_source.mdの仕様に厳密に準拠
- `BaseIO`は006で実装予定のため、004ではオプショナル引数として定義
- MockDataSourceは`BaseIO`を使用せず、直接モックデータを保持
- 日本語コメント・docstring必須（constitution準拠）
- 各フェーズ完了後に品質ゲートチェック（mypy, ruff, pytest）

---

# Tasks: 005-calculator-abc

**Input**: Design documents from `/specs/001-qeel-core/`
**Prerequisites**: plan.md (required), contracts/base_signal_calculator.md (required), data-model.md (required)

**Branch**: `005-calculator-abc`
**目的**: シグナル計算ABCとサンプル実装

**成果物**:
- `qeel/calculators/signals/base.py` - BaseSignalCalculator ABC
- `qeel/examples/signals/moving_average.py` - 移動平均クロス実装例
- Pydanticパラメータモデル（SignalCalculatorParams - 002で実装済み）

**Tests**: TDDを厳守。Red-Green-Refactorサイクル必須（constitution準拠）

**依存ブランチ**: `002-core-config-and-schemas`（完了済み）

**Note**:
- contracts/base_signal_calculator.mdの仕様に準拠して実装
- SignalCalculatorParamsは002で実装済みのため、importして使用
- SignalSchemaは002で実装済みのため、_validate_output()ヘルパーで使用
- 004のBaseDataSourceと同様のパターンでABCを設計

---

## Phase 14: Calculator Package Setup

**Purpose**: シグナル計算パッケージの初期化

- [x] T058 src/qeel/calculators/__init__.pyを作成（パッケージ初期化）
- [x] T059 [P] src/qeel/calculators/signals/__init__.pyを作成（サブパッケージ初期化）
- [x] T060 [P] src/qeel/examples/__init__.pyを作成（examples初期化）
- [x] T061 [P] src/qeel/examples/signals/__init__.pyを作成（examples/signals初期化）

**Checkpoint**: パッケージ構造完成

---

## Phase 15: BaseSignalCalculator ABC

**Purpose**: シグナル計算抽象基底クラスの実装

**テスト方針**: `_validate_output()`はprotectedメソッドだが、
ユーザがサブクラスで利用することを想定した公開APIの一部である。
テストでは具象サブクラス（テスト用スタブ）を作成し、メソッドを呼び出して検証する。

### Tests (TDD: RED)

- [x] T062 tests/unit/test_signal_calculator.pyを作成
  - `test_base_signal_calculator_cannot_instantiate`: ABCは直接インスタンス化不可
  - `test_calculate_is_abstract_method`: calculate()が抽象メソッドであることを確認
  - `test_validate_output_passes_valid_signal`: 有効なSignalSchemaでバリデーションパス（テスト用スタブ経由）
  - `test_validate_output_raises_missing_datetime`: datetime列欠損でValueError
  - `test_validate_output_raises_missing_symbol`: symbol列欠損でValueError
  - `test_validate_output_raises_wrong_dtype`: 型不一致でValueError
  - `test_validate_output_allows_extra_columns`: 追加列（signal, signal_momentum等）は許容
  - `test_params_is_stored_in_instance`: paramsがインスタンスに保存されることを確認

### Implementation (TDD: GREEN)

- [x] T063 src/qeel/calculators/signals/base.pyにBaseSignalCalculator ABCを実装（contracts/base_signal_calculator.md参照）
  - `__init__(self, params: SignalCalculatorParams)`: パラメータを保存
  - `calculate(self, data_sources: dict[str, pl.DataFrame]) -> pl.DataFrame`: 抽象メソッド
  - `_validate_output(self, signals: pl.DataFrame) -> pl.DataFrame`: 出力バリデーションヘルパー

**Checkpoint**: `uv run pytest tests/unit/test_signal_calculator.py -k "base"` 全件パス

---

## Phase 16: MovingAverageCrossCalculator Example

**Purpose**: シグナル計算実装例（移動平均クロス戦略）

### Tests (TDD: RED)

- [x] T064 tests/unit/test_signal_calculator.pyにテストを追加
  - `test_moving_average_cross_params_validation`: パラメータバリデーション確認（short_window > 0, long_window > 0）
  - `test_moving_average_cross_params_short_less_than_long`: short_window >= long_windowでValidationError
  - `test_moving_average_cross_calculate_returns_signal`: モックOHLCVからシグナルを計算
  - `test_moving_average_cross_raises_missing_ohlcv`: ohlcvデータソースが欠損でValueError
  - `test_moving_average_cross_output_has_required_columns`: 出力にdatetime, symbol, signal列が含まれる
  - `test_moving_average_cross_output_schema_valid`: 出力がSignalSchemaに準拠

### Implementation (TDD: GREEN)

- [x] T065 src/qeel/examples/signals/moving_average.pyにMovingAverageCrossParamsを実装
  - `short_window: int = Field(..., gt=0)`: 短期移動平均window
  - `long_window: int = Field(..., gt=0)`: 長期移動平均window
  - `model_validator`: short_window < long_window を検証（移動平均クロス戦略の前提条件）

- [x] T066 src/qeel/examples/signals/moving_average.pyにMovingAverageCrossCalculatorを実装
  - BaseSignalCalculatorを継承
  - calculate()でOHLCVから移動平均クロスシグナルを計算
  - _validate_output()でスキーマバリデーションを実行

**Checkpoint**: `uv run pytest tests/unit/test_signal_calculator.py -k "moving_average"` 全件パス

---

## Phase 17: Calculator Module Exports and Integration

**Purpose**: モジュールエクスポートと統合テスト

### Tests (TDD: RED)

- [x] T067 tests/integration/test_signal_calculator_integration.pyを作成
  - `test_calculator_with_mock_data_source`: MockDataSourceからデータを取得し、シグナル計算を実行
  - `test_calculator_output_schema_valid_for_context`: シグナル出力がSignalSchemaに準拠し、Context.signals（006で実装予定）に設定可能な形式であることを確認

### Implementation (TDD: GREEN)

- [x] T068 src/qeel/calculators/__init__.pyにexportを追加
- [x] T069 src/qeel/calculators/signals/__init__.pyにBaseSignalCalculatorをエクスポート
- [x] T070 src/qeel/examples/signals/__init__.pyにMovingAverageCrossCalculator, MovingAverageCrossParamsをエクスポート
- [x] T071 src/qeel/__init__.pyにcalculatorsモジュールを追加（必要に応じて）

**Checkpoint**: `uv run pytest tests/integration/test_signal_calculator_integration.py` 全件パス

---

## Phase 18: Quality Assurance for 005

**Purpose**: 品質チェックと最終確認

- [x] T072 `uv run mypy src/qeel/calculators/` で型エラーゼロを確認
- [x] T073 [P] `uv run mypy src/qeel/examples/` で型エラーゼロを確認
- [x] T074 `uv run ruff check src/qeel/calculators/ src/qeel/examples/` でリンターエラーゼロを確認
- [x] T075 `uv run ruff format src/qeel/calculators/ src/qeel/examples/` でフォーマット適用
- [x] T076 `uv run pytest` で全テストパスを確認（002, 004のテストも含む）

---

## Dependencies & Execution Order (005)

### Phase Dependencies

- **Phase 14 (Package Setup)**: 002完了後 - 即開始可能
- **Phase 15 (BaseSignalCalculator ABC)**: Phase 14完了後
- **Phase 16 (MovingAverageCross Example)**: Phase 15完了後
- **Phase 17 (Integration)**: Phase 16完了後
- **Phase 18 (QA)**: Phase 17完了後

### Execution Flow

```
002-core-config-and-schemas (完了)
            |
            v
       Phase 14 (Setup)
            |
            v
       Phase 15 (ABC)
            |
            v
       Phase 16 (Example)
            |
            v
       Phase 17 (Integration)
            |
            v
       Phase 18 (QA)
```

### Within Each Phase

- テストを先に作成し、失敗を確認（RED）
- 実装してテストをパス（GREEN）
- 必要に応じてリファクタリング（REFACTOR）

---

## Task Summary (005)

- **Total Tasks (005)**: 19 (T058-T076)
- **Setup Tasks**: 4
- **ABC Tasks**: 2 (tests + impl)
- **Example Tasks**: 3 (tests + impl)
- **Integration Tasks**: 5 (tests + impl)
- **QA Tasks**: 5

**Parallel Opportunities**:
- Phase 14内のT059, T060, T061は並列実行可能
- Phase 18内のT072, T073は並列実行可能

---

## Implementation Strategy (005)

### MVP (最小実装)

1. Phase 14: Package Setup完了
2. Phase 15: BaseSignalCalculator ABC完了
3. Phase 18: QA実行

この時点でABCが定義され、ユーザはカスタムシグナル計算ロジックを実装可能

### Full Implementation

1. MVP完了後
2. Phase 16: MovingAverageCrossCalculator完了（実装例）
3. Phase 17: Integration完了
4. Phase 18: 最終QA

---

## Notes (005)

- contracts/base_signal_calculator.mdの仕様に厳密に準拠
- SignalCalculatorParams（002で実装済み）をimportして使用
- SignalSchema（002で実装済み）を_validate_output()で使用
- 日本語コメント・docstring必須（constitution準拠）
- 各フェーズ完了後に品質ゲートチェック（mypy, ruff, pytest）
- BaseDataSource（004）と同様のABCパターンを踏襲
