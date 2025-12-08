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

# Tasks: 007-exchange-client-and-mock

**Input**: Design documents from `/specs/001-qeel-core/`
**Prerequisites**: plan.md (required), contracts/base_exchange_client.md (required), data-model.md (required)

**Branch**: `007-exchange-client-and-mock`
**目的**: 取引所クライアントABCとモック約定・ポジション管理

**成果物**:
- `qeel/exchange_clients/base.py` - BaseExchangeClient ABC
  - `_validate_orders()`: 注文DataFrameの共通バリデーション
  - `_validate_fills()`: 約定情報DataFrameの共通バリデーション
  - `_validate_positions()`: ポジション情報DataFrameの共通バリデーション
  - `submit_orders()`: 抽象メソッド
  - `fetch_fills()`: 抽象メソッド
  - `fetch_positions()`: 抽象メソッド
- `qeel/exchange_clients/mock.py` - MockExchangeClient（バックテスト用）
  - コスト計算ロジック（手数料、スリッページ）
  - 約定履歴からのポジション計算

**Tests**: TDDを厳守。Red-Green-Refactorサイクル必須（constitution準拠）

**依存ブランチ**: `002-core-config-and-schemas`（完了済み）

**Note**:
- contracts/base_exchange_client.mdの仕様に準拠して実装
- CostConfig（002で実装済み）を使用してコスト計算
- OrderSchema, FillReportSchema, PositionSchema（002で実装済み）を_validate_*()ヘルパーで使用
- 004のBaseDataSource、005のBaseSignalCalculatorと同様のABCパターンを踏襲
- バックテスト時は丸めをスキップ（理想的な約定を想定）

---

## Phase 29: Exchange Client Package Setup

**Purpose**: exchange_clientsパッケージの初期化

- [ ] T105 src/qeel/exchange_clients/__init__.pyを作成（パッケージ初期化）

**Checkpoint**: パッケージ構造完成

---

## Phase 30: BaseExchangeClient ABC

**Purpose**: 取引所クライアント抽象基底クラスの実装

**テスト方針**: ヘルパーメソッド（`_validate_orders`等）はprotectedメソッドだが、
ユーザがサブクラスで利用することを想定した公開APIの一部である。
テストでは具象サブクラス（テスト用スタブ）を作成し、ヘルパーメソッドを呼び出して検証する。

### Tests (TDD: RED)

- [ ] T106 tests/unit/test_exchange_client.pyを作成
  - `test_base_exchange_client_cannot_instantiate`: ABCは直接インスタンス化不可
  - `test_submit_orders_is_abstract_method`: submit_orders()が抽象メソッドであることを確認
  - `test_fetch_fills_is_abstract_method`: fetch_fills()が抽象メソッドであることを確認
  - `test_fetch_positions_is_abstract_method`: fetch_positions()が抽象メソッドであることを確認
  - `test_validate_orders_passes_valid_order`: 有効なOrderSchemaでバリデーションパス（テスト用スタブ経由）
  - `test_validate_orders_raises_missing_column`: 必須列欠損でValueError
  - `test_validate_orders_raises_invalid_side`: 不正なside値でValueError
  - `test_validate_orders_raises_invalid_order_type`: 不正なorder_type値でValueError
  - `test_validate_fills_passes_valid_fill`: 有効なFillReportSchemaでバリデーションパス
  - `test_validate_fills_raises_missing_column`: 必須列欠損でValueError
  - `test_validate_fills_raises_wrong_dtype`: 型不一致でValueError
  - `test_validate_positions_passes_valid_position`: 有効なPositionSchemaでバリデーションパス
  - `test_validate_positions_raises_missing_column`: 必須列欠損でValueError
  - `test_validate_positions_raises_wrong_dtype`: 型不一致でValueError

### Implementation (TDD: GREEN)

- [ ] T107 src/qeel/exchange_clients/base.pyにBaseExchangeClient ABCを実装（contracts/base_exchange_client.md参照）
  - `_validate_orders(self, orders: pl.DataFrame) -> None`: OrderSchemaバリデーション
  - `_validate_fills(self, fills: pl.DataFrame) -> pl.DataFrame`: FillReportSchemaバリデーション
  - `_validate_positions(self, positions: pl.DataFrame) -> pl.DataFrame`: PositionSchemaバリデーション
  - `submit_orders(self, orders: pl.DataFrame) -> None`: 抽象メソッド
  - `fetch_fills(self) -> pl.DataFrame`: 抽象メソッド
  - `fetch_positions(self) -> pl.DataFrame`: 抽象メソッド

**Checkpoint**: `uv run pytest tests/unit/test_exchange_client.py -k "base"` 全件パス

---

## Phase 31: MockExchangeClient

**Purpose**: バックテスト用モック取引所クライアントの実装

### Tests (TDD: RED)

- [ ] T108 tests/unit/test_exchange_client.pyにテストを追加
  - `test_mock_exchange_client_submit_orders_stores_fills`: submit_orders()で約定がpending_fillsに追加される
  - `test_mock_exchange_client_submit_orders_validates_input`: 不正な注文でValueError
  - `test_mock_exchange_client_fetch_fills_returns_dataframe`: fetch_fills()がFillReportSchema準拠のDataFrameを返す
  - `test_mock_exchange_client_fetch_fills_clears_pending`: fetch_fills()後、pending_fillsがクリアされる
  - `test_mock_exchange_client_fetch_fills_empty_returns_empty_dataframe`: 約定がない場合は空DataFrame（スキーマ付き）
  - `test_mock_exchange_client_applies_commission`: 手数料が正しく計算される
  - `test_mock_exchange_client_applies_slippage_buy`: 買い注文でスリッページが価格を上昇させる
  - `test_mock_exchange_client_applies_slippage_sell`: 売り注文でスリッページが価格を下落させる
  - `test_mock_exchange_client_fetch_positions_returns_dataframe`: fetch_positions()がPositionSchema準拠のDataFrameを返す
  - `test_mock_exchange_client_fetch_positions_calculates_from_history`: 約定履歴から正しくポジションを計算
  - `test_mock_exchange_client_fetch_positions_buy_increases_quantity`: 買い約定でポジション数量が増加
  - `test_mock_exchange_client_fetch_positions_sell_decreases_quantity`: 売り約定でポジション数量が減少
  - `test_mock_exchange_client_fetch_positions_filters_zero_quantity`: 数量ゼロのポジションは除外される
  - `test_mock_exchange_client_fetch_positions_empty_returns_empty_dataframe`: 約定履歴がない場合は空DataFrame

### Implementation (TDD: GREEN)

- [ ] T109 src/qeel/exchange_clients/mock.pyにMockExchangeClientを実装（contracts/base_exchange_client.md参照）
  - `__init__(self, config: CostConfig)`: CostConfigを受け取る
  - `pending_fills: list[pl.DataFrame]`: 未取得の約定リスト
  - `fill_history: list[pl.DataFrame]`: ポジション計算用の約定履歴
  - `submit_orders(self, orders: pl.DataFrame) -> None`: 全注文を即座に約定として処理
  - `fetch_fills(self) -> pl.DataFrame`: pending_fillsを返し、クリア
  - `fetch_positions(self) -> pl.DataFrame`: fill_historyからポジションを計算
  - 手数料計算: `quantity * price * commission_rate`
  - スリッページ計算: 買いは`price * (1 + slippage_bps / 10000)`、売りは`price * (1 - slippage_bps / 10000)`

**Checkpoint**: `uv run pytest tests/unit/test_exchange_client.py -k "mock"` 全件パス

---

## Phase 32: Exchange Client Module Exports and Integration

**Purpose**: モジュールエクスポートと統合テスト

### Tests (TDD: RED)

- [ ] T110 tests/integration/test_exchange_client_integration.pyを作成
  - `test_mock_exchange_client_with_cost_config`: CostConfigを使用してMockExchangeClientを初期化し、submit_orders/fetch_fills/fetch_positionsが正常動作
  - `test_mock_exchange_client_full_trade_cycle`: 完全なトレードサイクル（買い→ポジション確認→売り→ポジション確認）
  - `test_context_store_load_with_mock_exchange_client`: ContextStore.load()がMockExchangeClientを使用してコンテキストを復元

### Implementation (TDD: GREEN)

- [ ] T111 src/qeel/exchange_clients/__init__.pyにBaseExchangeClient, MockExchangeClientをエクスポート
- [ ] T112 src/qeel/__init__.pyにexchange_clientsモジュールを追加（必要に応じて）

**Checkpoint**: `uv run pytest tests/integration/test_exchange_client_integration.py` 全件パス

---

## Phase 33: Quality Assurance for 007

**Purpose**: 品質チェックと最終確認

- [ ] T113 `uv run mypy src/qeel/exchange_clients/` で型エラーゼロを確認
- [ ] T114 `uv run ruff check src/qeel/exchange_clients/` でリンターエラーゼロを確認
- [ ] T115 `uv run ruff format src/qeel/exchange_clients/` でフォーマット適用
- [ ] T116 `uv run pytest` で全テストパスを確認（002, 004, 005, 006のテストも含む）

---

## Dependencies & Execution Order (007)

### Phase Dependencies

- **Phase 29 (Package Setup)**: 006完了後 - 即開始可能
- **Phase 30 (BaseExchangeClient ABC)**: Phase 29完了後
- **Phase 31 (MockExchangeClient)**: Phase 30完了後
- **Phase 32 (Integration)**: Phase 31完了後
- **Phase 33 (QA)**: Phase 32完了後

### Execution Flow

```
006-io-and-context-management (完了)
            |
            v
       Phase 29 (Setup)
            |
            v
       Phase 30 (ABC)
            |
            v
       Phase 31 (Mock)
            |
            v
       Phase 32 (Integration)
            |
            v
       Phase 33 (QA)
```

### Within Each Phase

- テストを先に作成し、失敗を確認（RED）
- 実装してテストをパス（GREEN）
- 必要に応じてリファクタリング（REFACTOR）

---

## Task Summary (007)

- **Total Tasks (007)**: 12 (T105-T116)
- **Setup Tasks**: 1
- **ABC Tasks**: 2 (tests + impl)
- **Mock Tasks**: 2 (tests + impl)
- **Integration Tasks**: 3 (tests + impl)
- **QA Tasks**: 4

**Parallel Opportunities**:
- Phase 30内のテストケースは並列で作成可能
- Phase 31内のテストケースは並列で作成可能

---

## Implementation Strategy (007)

### MVP (最小実装)

1. Phase 29: Package Setup完了
2. Phase 30: BaseExchangeClient ABC完了
3. Phase 33: QA実行

この時点でABCが定義され、ユーザはカスタム取引所クライアント（取引所API実装）を作成可能

### Full Implementation

1. MVP完了後
2. Phase 31: MockExchangeClient完了（バックテスト用）
3. Phase 32: Integration完了
4. Phase 33: 最終QA

---

## Notes (007)

- contracts/base_exchange_client.mdの仕様に厳密に準拠
- CostConfig（002で実装済み）のcommission_rate, slippage_bpsを使用
- OrderSchema, FillReportSchema, PositionSchema（002で実装済み）を_validate_*()ヘルパーで使用
- 日本語コメント・docstring必須（constitution準拠）
- 各フェーズ完了後に品質ゲートチェック（mypy, ruff, pytest）
- BaseDataSource（004）、BaseSignalCalculator（005）、BaseIO（006）と同様のABCパターンを踏襲
- MockExchangeClientはContextStore.load()で使用されるため、このブランチ完了後に006のContextStoreテストが完全に動作する
