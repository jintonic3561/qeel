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
