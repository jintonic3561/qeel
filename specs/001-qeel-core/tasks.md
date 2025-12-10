# Implementation Branch Status

実装ブランチの進捗一覧。完了済みタスクの詳細は `tasks_archive.md` を参照。

## Phase 1: Core Infrastructure（基盤構築）

- [x] **002-core-config-and-schemas** - 設定管理とスキーマバリデーションの基盤 (T001-T045)
- [x] **004-data-source-abc** - データソースABCと共通ヘルパーメソッド (T046-T057)
- [x] **005-calculator-abc** - シグナル計算ABCとサンプル実装 (T058-T076)
- [x] **006-io-and-context-management** - IOレイヤーとコンテキスト管理 (T077-T104)
- [x] **007-exchange-client-and-mock** - 取引所クライアントABCとモック約定・ポジション管理 (T105-T144)

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

## Branch 008: Portfolio & Orders - ポートフォリオ構築・注文生成のABCとデフォルト実装 (T145-T181)

**Input**: Design documents from `/specs/001-qeel-core/`
**Prerequisites**: 002-core-config-and-schemas (完了), contracts/base_portfolio_constructor.md, contracts/base_entry_order_creator.md, contracts/base_exit_order_creator.md

**User Story対応**: User Story 1（ポートフォリオ構築、注文生成）- P1

**目的**: ポートフォリオ構築・注文生成のABCとデフォルト実装を提供する

**成果物**:
- `qeel/portfolio_constructors/base.py` - BasePortfolioConstructor ABC
- `qeel/portfolio_constructors/top_n.py` - TopNPortfolioConstructor（デフォルト実装）
- `qeel/entry_order_creators/base.py` - BaseEntryOrderCreator ABC
- `qeel/entry_order_creators/equal_weight.py` - EqualWeightEntryOrderCreator（デフォルト実装）
- `qeel/exit_order_creators/base.py` - BaseExitOrderCreator ABC
- `qeel/exit_order_creators/full_exit.py` - FullExitOrderCreator（デフォルト実装）

---

### Phase 1: Setup

**Purpose**: ディレクトリ構造の作成

- [x] T145 ポートフォリオ構築用ディレクトリ作成: `src/qeel/portfolio_constructors/`
- [x] T146 [P] エントリー注文生成用ディレクトリ作成: `src/qeel/entry_order_creators/`
- [x] T147 [P] エグジット注文生成用ディレクトリ作成: `src/qeel/exit_order_creators/`

---

### Phase 2: BasePortfolioConstructor ABC

**Purpose**: ポートフォリオ構築の抽象基底クラス実装

#### Tests（TDD: Red）

- [x] T148 [P] [US1] BasePortfolioConstructorの単体テスト作成: `tests/unit/test_portfolio_constructors.py`
  - 入力バリデーション（`_validate_inputs`）が正しく動作することを確認
  - 出力バリデーション（`_validate_output`）が正しく動作することを確認
  - ABC継承のテスト（抽象メソッドの実装強制を確認）

#### Implementation（TDD: Green）

- [x] T149 [US1] BasePortfolioConstructor ABC実装: `src/qeel/portfolio_constructors/base.py`
  - `__init__(params: PortfolioConstructorParams)`
  - `_validate_inputs(signals, current_positions)`: 入力バリデーションヘルパー
  - `_validate_output(portfolio)`: 出力バリデーションヘルパー
  - `construct(signals, current_positions) -> pl.DataFrame`: 抽象メソッド
  - contracts/base_portfolio_constructor.md準拠

- [x] T150 [US1] `__init__.py`作成とエクスポート設定: `src/qeel/portfolio_constructors/__init__.py`

---

### Phase 3: TopNPortfolioConstructor デフォルト実装

**Purpose**: シグナル上位N銘柄でポートフォリオを構築するデフォルト実装

#### Tests（TDD: Red）

- [x] T151 [P] [US1] TopNPortfolioConstructorの単体テスト追加: `tests/unit/test_portfolio_constructors.py`
  - パラメータ（top_n, ascending）の動作確認
  - シグナル上位N銘柄が選定されることを確認
  - signal_strengthがメタデータとして含まれることを確認
  - 空のシグナルDataFrameに対して空のDataFrameを返すことを確認
  - シグナル数がtop_n未満の場合の動作確認

#### Implementation（TDD: Green）

- [x] T152 [US1] TopNConstructorParams実装: `src/qeel/portfolio_constructors/top_n.py`
  - `top_n: int = Field(default=10, gt=0)`
  - `ascending: bool = Field(default=False)`

- [x] T153 [US1] TopNPortfolioConstructor実装: `src/qeel/portfolio_constructors/top_n.py`
  - `construct(signals, current_positions)`: シグナル上位N銘柄選定
  - 出力に`datetime`, `symbol`, `signal_strength`を含む
  - contracts/base_portfolio_constructor.md準拠

- [x] T154 [US1] `__init__.py`にTopN関連クラスのエクスポート追加: `src/qeel/portfolio_constructors/__init__.py`

---

### Phase 4: BaseEntryOrderCreator ABC

**Purpose**: エントリー注文生成の抽象基底クラス実装

#### Tests（TDD: Red）

- [x] T155 [P] [US1] BaseEntryOrderCreatorの単体テスト作成: `tests/unit/test_entry_order_creators.py`
  - 入力バリデーション（`_validate_inputs`）が正しく動作することを確認
  - ABC継承のテスト（抽象メソッドの実装強制を確認）

#### Implementation（TDD: Green）

- [x] T156 [US1] BaseEntryOrderCreator ABC実装: `src/qeel/entry_order_creators/base.py`
  - `__init__(params: EntryOrderCreatorParams)`
  - `_validate_inputs(portfolio_plan, current_positions, ohlcv)`: 入力バリデーションヘルパー
  - `create(portfolio_plan, current_positions, ohlcv) -> pl.DataFrame`: 抽象メソッド
  - contracts/base_entry_order_creator.md準拠

- [x] T157 [US1] `__init__.py`作成とエクスポート設定: `src/qeel/entry_order_creators/__init__.py`

---

### Phase 5: EqualWeightEntryOrderCreator デフォルト実装

**Purpose**: 等ウェイトポートフォリオでエントリー注文を生成するデフォルト実装

#### Tests（TDD: Red）

- [x] T158 [P] [US1] EqualWeightEntryOrderCreatorの単体テスト追加: `tests/unit/test_entry_order_creators.py`
  - パラメータ（capital, rebalance_threshold）の動作確認
  - 等ウェイト配分で注文が生成されることを確認
  - 成行注文（order_type="market", price=None）が生成されることを確認
  - signal_strengthを参照して買い/売りを決定することを確認
  - 空のportfolio_planに対して空のDataFrameを返すことを確認
  - 価格データがない銘柄がスキップされることを確認

#### Implementation（TDD: Green）

- [x] T159 [US1] EqualWeightEntryParams実装: `src/qeel/entry_order_creators/equal_weight.py`
  - `capital: float = Field(default=1_000_000.0, gt=0.0)`
  - `rebalance_threshold: float = Field(default=0.05, ge=0.0, le=1.0)`

- [x] T160 [US1] EqualWeightEntryOrderCreator実装: `src/qeel/entry_order_creators/equal_weight.py`
  - `create(portfolio_plan, current_positions, ohlcv)`: 等ウェイト注文生成
  - open価格で成行注文を生成
  - signal_strengthを参照して買い/売りを決定
  - contracts/base_entry_order_creator.md準拠

- [x] T161 [US1] `__init__.py`にEqualWeight関連クラスのエクスポート追加: `src/qeel/entry_order_creators/__init__.py`

---

### Phase 6: BaseExitOrderCreator ABC

**Purpose**: エグジット注文生成の抽象基底クラス実装

#### Tests（TDD: Red）

- [ ] T162 [P] [US1] BaseExitOrderCreatorの単体テスト作成: `tests/unit/test_exit_order_creators.py`
  - 入力バリデーション（`_validate_inputs`）が正しく動作することを確認
  - ABC継承のテスト（抽象メソッドの実装強制を確認）

#### Implementation（TDD: Green）

- [ ] T163 [US1] BaseExitOrderCreator ABC実装: `src/qeel/exit_order_creators/base.py`
  - `__init__(params: ExitOrderCreatorParams)`
  - `_validate_inputs(current_positions, ohlcv)`: 入力バリデーションヘルパー
  - `create(current_positions, ohlcv) -> pl.DataFrame`: 抽象メソッド
  - contracts/base_exit_order_creator.md準拠

- [ ] T164 [US1] `__init__.py`作成とエクスポート設定: `src/qeel/exit_order_creators/__init__.py`

---

### Phase 7: FullExitOrderCreator デフォルト実装

**Purpose**: 全ポジション決済注文を生成するデフォルト実装

#### Tests（TDD: Red）

- [ ] T165 [P] [US1] FullExitOrderCreatorの単体テスト追加: `tests/unit/test_exit_order_creators.py`
  - パラメータ（exit_threshold）の動作確認
  - 保有ポジション全決済の注文が生成されることを確認
  - 成行注文（order_type="market", price=None）が生成されることを確認
  - 買いポジションは売り、売りポジションは買いで決済されることを確認
  - exit_thresholdに応じて決済数量が調整されることを確認
  - 空のポジションに対して空のDataFrameを返すことを確認
  - 価格データがない銘柄がスキップされることを確認
  - quantity=0のポジションがスキップされることを確認

#### Implementation（TDD: Green）

- [ ] T166 [US1] FullExitParams実装: `src/qeel/exit_order_creators/full_exit.py`
  - `exit_threshold: float = Field(default=1.0, ge=0.0, le=1.0)`

- [ ] T167 [US1] FullExitOrderCreator実装: `src/qeel/exit_order_creators/full_exit.py`
  - `create(current_positions, ohlcv)`: 全決済注文生成
  - close価格で成行注文を生成
  - exit_thresholdで決済比率を調整
  - contracts/base_exit_order_creator.md準拠

- [ ] T168 [US1] `__init__.py`にFullExit関連クラスのエクスポート追加: `src/qeel/exit_order_creators/__init__.py`

---

### Phase 8: 統合テスト

**Purpose**: ポートフォリオ構築から注文生成までのフロー確認

#### Tests（TDD: Red → Green）

- [ ] T169 [US1] 統合テスト作成: `tests/integration/test_portfolio_order_integration.py`
  - TopNPortfolioConstructor → EqualWeightEntryOrderCreator のフロー確認
  - TopNPortfolioConstructor → FullExitOrderCreator のフロー確認
  - signal_strengthメタデータがエントリー注文生成で正しく参照されることを確認

---

### Phase 9: Polish & 品質ゲート

**Purpose**: コード品質の確保

- [ ] T170 mypy strictモードでの型チェック実行
- [ ] T171 [P] ruff check & format実行
- [ ] T172 [P] pytest全件パス確認
- [ ] T173 `__init__.py`でのパブリックAPI整理
  - `src/qeel/portfolio_constructors/__init__.py`
  - `src/qeel/entry_order_creators/__init__.py`
  - `src/qeel/exit_order_creators/__init__.py`

---

### Dependencies & Execution Order

**Phase Dependencies**:
- Phase 1 (Setup): 依存なし
- Phase 2 (BasePortfolioConstructor): Phase 1完了後
- Phase 3 (TopNPortfolioConstructor): Phase 2完了後
- Phase 4 (BaseEntryOrderCreator): Phase 1完了後（Phase 2と並行可能）
- Phase 5 (EqualWeightEntryOrderCreator): Phase 4完了後
- Phase 6 (BaseExitOrderCreator): Phase 1完了後（Phase 2, 4と並行可能）
- Phase 7 (FullExitOrderCreator): Phase 6完了後
- Phase 8 (統合テスト): Phase 3, 5, 7すべて完了後
- Phase 9 (Polish): Phase 8完了後

**Parallel Opportunities**:
- T145, T146, T147: すべて並行実行可能
- T148 & T155 & T162: 各ABCのテストは並行実行可能
- T151 & T158 & T165: 各デフォルト実装のテストは並行実行可能

**既存実装との依存関係**:
- `qeel.schemas.validators`: SignalSchema, PositionSchema, PortfolioSchema, OrderSchema, OHLCVSchema（002で実装済み）
- `qeel.config.params`: PortfolioConstructorParams, EntryOrderCreatorParams, ExitOrderCreatorParams（002で実装済み）

---

### Summary

| カテゴリ | タスク数 |
|---------|---------|
| Setup | 3 |
| BasePortfolioConstructor | 3 |
| TopNPortfolioConstructor | 4 |
| BaseEntryOrderCreator | 3 |
| EqualWeightEntryOrderCreator | 4 |
| BaseExitOrderCreator | 3 |
| FullExitOrderCreator | 4 |
| 統合テスト | 1 |
| Polish | 4 |
| **合計** | **29** |

**タスク番号範囲**: T145-T173
