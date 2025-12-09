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
