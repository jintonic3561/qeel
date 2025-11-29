# Implementation Tasks: Qeel - 量的トレーディング向けバックテストライブラリ

**Branch**: `001-qeel-core`
**Date**: 2025-11-26
**Status**: Planning

## 重要な注意事項

**このブランチ（001-qeel-core）では実装を行いません。**

このブランチの目的は、プロジェクト全体の俯瞰的な設計と機能ブランチ戦略の策定です。実際の実装は、以下に定義する各機能ブランチで段階的に行います。

各機能ブランチでは：
1. そのブランチ専用の詳細なspecを立てる（必要に応じて `/speckit.specify`）
2. そのブランチ専用のtasks.mdを生成する（`/speckit.tasks`）
3. TDDで実装する（`/speckit.implement`）

---

## Phase 1: プロジェクト基盤の策定（このブランチ）

### 目標

プロジェクト全体の設計方針、アーキテクチャ、機能ブランチ戦略を確立し、実装の準備を整える。

### タスク

- [x] T001 仕様書を作成（spec.md）
- [x] T002 仕様の曖昧性を解消（/speckit.clarify）
- [x] T003 技術調査とベストプラクティス研究（research.md）
- [x] T004 データモデル設計（data-model.md）
- [x] T005 ABCインターフェース仕様策定（contracts/）
- [x] T006 ユーザ向けクイックスタートガイド作成（quickstart.md）
- [x] T007 機能ブランチ戦略策定（plan.md）
- [ ] T008 このタスクファイル作成（tasks.md）
- [ ] T009 プロジェクト基盤をコミット

---

## Phase 2: 機能ブランチの作成と実装（以降のブランチ）

以下のフェーズは、**それぞれ独立した機能ブランチ**で実装されます。
各ブランチは独立してテスト・マージ可能で、User Story単位での段階的デリバリーを実現します。

---

### Phase 2.1: Core Infrastructure（基盤構築）

#### Branch 002: 設定管理とスキーマバリデーション

**Branch Name**: `002-core-config-and-schemas`
**目的**: Pydantic設定モデルとPolarsスキーマバリデーションの基盤構築
**依存**: なし
**User Story**: N/A（基盤）

**このブランチで実施する作業**:

- [ ] T010 ブランチ作成: `git checkout -b 002-core-config-and-schemas`
- [ ] T011 このブランチ専用のspec作成（必要に応じて）
- [ ] T012 このブランチ専用のtasks.md生成: `/speckit.tasks`
- [ ] T013 TDD実装: `/speckit.implement`（以下を含む）
  - pyproject.toml、mypy.ini作成
  - src/qeel/__init__.py作成
  - src/qeel/config/models.py: Config, DataSourceConfig, CostConfig, LoopConfig
  - src/qeel/schemas/validators.py: MarketDataSchema, SignalSchema等
  - tests/unit/test_config.py
  - tests/unit/test_schemas.py
- [ ] T014 mypy strictモードでの型チェック合格
- [ ] T015 PRを作成しマージ

**完了条件**:
- toml設定ファイルの読み込みとバリデーションが動作
- 不正なtomlでValidationError、正常なtomlで正しくロード
- すべてのスキーマバリデータが期待通りに動作

---

#### Branch 002a: Utilsインフラストラクチャ

**Branch Name**: `002a-utils-infrastructure`
**目的**: 実運用Executor実装を支援するユーティリティ群
**依存**: `002-core-config-and-schemas`
**User Story**: User Story 2（実運用支援、オプション機能）

**このブランチで実施する作業**:

- [ ] T015a ブランチ作成: `git checkout -b 002a-utils-infrastructure`
- [ ] T015b このブランチ専用のtasks.md生成: `/speckit.tasks`
- [ ] T015c TDD実装: `/speckit.implement`（以下を含む）
  - src/qeel/utils/__init__.py作成
  - src/qeel/utils/retry.py: with_retry関数（exponential backoff、タイムアウト）
  - src/qeel/utils/notification.py: send_slack_notification関数
  - src/qeel/utils/rounding.py: round_to_unit(value, unit)関数（汎用丸め処理）
  - tests/unit/test_utils_retry.py（モックAPIクライアントでリトライ動作確認）
  - tests/unit/test_utils_notification.py（モック通知送信確認）
  - tests/unit/test_utils_rounding.py（丸め処理の精度検証: unit=0.01, 1.0, 0.001等）
- [ ] T015d 型ヒント完備、可読性重視の実装確認
- [ ] T015e PRを作成しマージ

**完了条件**:
- リトライ機能が正しく動作（exponential backoff、タイムアウト）
- Slack通知が正しく送信される（モック確認）
- 丸め処理が正しく動作（任意のunit指定で丸められる）
- ユーザが簡単に利用できるインターフェース

---

#### Branch 003: データソースABC

**Branch Name**: `003-data-source-abc`
**目的**: データソース抽象基底クラスと共通ヘルパーメソッド、テスト用実装
**依存**: `002-core-config-and-schemas`
**User Story**: N/A（User Story 1で使用）

**このブランチで実施する作業**:

- [ ] T016 ブランチ作成: `git checkout -b 003-data-source-abc`
- [ ] T017 このブランチ専用のtasks.md生成
- [ ] T018 TDD実装（以下を含む）
  - src/qeel/data_sources/base.py: BaseDataSource ABC
    - `_normalize_datetime_column()`: datetime列の正規化
    - `_adjust_window_for_offset()`: offset_secondsによるwindow調整（リーク防止）
    - `_filter_by_datetime_and_symbols()`: datetime範囲と銘柄でフィルタリング
  - src/qeel/data_sources/mock.py: MockDataSource（テスト用、ヘルパーメソッド使用例）
  - tests/unit/test_data_sources.py（ヘルパーメソッドの動作確認含む）
  - tests/contract/test_data_source_contract.py
- [ ] T019 PRを作成しマージ

**完了条件**:
- モックデータでfetch()が正しく動作
- 共通ヘルパーメソッドが期待通りに動作（datetime正規化、window調整、フィルタリング）
- ユーザは任意のスキーマを返すことができ、システムは強制的なバリデーションを行わない
- offset処理がdatetime列上書きではなくwindow調整で実装されている（リーク防止）

---

#### Branch 004: シグナル計算ABC

**Branch Name**: `004-calculator-abc`
**目的**: シグナル計算抽象基底クラスとサンプル実装
**依存**: `002-core-config-and-schemas`
**User Story**: User Story 1（シグナル計算）

**このブランチで実施する作業**:

- [ ] T020 ブランチ作成: `git checkout -b 004-calculator-abc`
- [ ] T021 このブランチ専用のtasks.md生成
- [ ] T022 TDD実装（以下を含む）
  - src/qeel/calculators/signals/base.py: BaseSignalCalculator ABC
  - src/qeel/calculators/signals/examples/moving_average.py: 移動平均クロス実装例
  - tests/unit/test_calculators.py
  - tests/contract/test_signal_calculator_contract.py
- [ ] T023 PRを作成しマージ

**完了条件**:
- モックデータでcalculate()が正しく動作
- サンプル実装が期待通りのシグナルを生成

---

#### Branch 005: コンテキスト管理

**Branch Name**: `005-context-management`
**目的**: iteration間コンテキストの永続化
**依存**: `002-core-config-and-schemas`
**User Story**: User Story 1（コンテキスト永続化）

**このブランチで実施する作業**:

- [ ] T024 ブランチ作成: `git checkout -b 005-context-management`
- [ ] T025 このブランチ専用のtasks.md生成
- [ ] T026 TDD実装（以下を含む）
  - src/qeel/models/context.py: Context Pydanticモデル
  - src/qeel/stores/base.py: BaseContextStore ABC
  - src/qeel/stores/local.py: LocalStore（JSON/Parquet両対応、フォーマット指定可能）
  - src/qeel/stores/s3.py: S3Store（JSON/Parquet両対応、boto3使用、実運用必須）
  - src/qeel/stores/in_memory.py: InMemoryStore（テスト用）
  - tests/unit/test_stores.py（LocalStoreはJSON/Parquet両方テスト、S3はモックboto3で動作確認）
  - tests/contract/test_context_store_contract.py
- [ ] T027 PRを作成しマージ

**完了条件**:
- LocalStore: save/load/load_latestがJSON/Parquet両方で正しく動作
- S3Store: save/load/load_latestがJSON/Parquet両方で正しく動作、モックboto3で動作確認（put_object/get_object呼び出し確認）
- load()は指定日付のコンテキストを返す、load_latest()は最新日付のコンテキストを返す
- 存在しない場合はNoneを返す

---

#### Branch 006: 執行ABC

**Branch Name**: `006-executor-and-mock`
**目的**: 執行ABCとモック約定シミュレーション
**依存**: `002-core-config-and-schemas`
**User Story**: User Story 1（約定シミュレーション）

**このブランチで実施する作業**:

- [ ] T028 ブランチ作成: `git checkout -b 006-executor-and-mock`
- [ ] T029 このブランチ専用のtasks.md生成
- [ ] T030 TDD実装（以下を含む）
  - src/qeel/executors/base.py: BaseExecutor ABC
  - src/qeel/executors/mock.py: MockExecutor（バックテスト用）
  - コスト計算ロジック（手数料、スリッページ）
  - tests/unit/test_executors.py
  - tests/contract/test_executor_contract.py
- [ ] T031 PRを作成しマージ

**完了条件**:
- モック約定が正しく生成される
- コストが正しく反映される

---

### Phase 2.2: User Story 1（P1）- バックテストの実行と結果検証

#### Branch 007: バックテストエンジン本体

**Branch Name**: `007-backtest-engine`
**目的**: バックテストエンジン実装（P1完成）
**依存**: `003`, `004`, `005`, `006`
**User Story**: **User Story 1（P1）**

**このブランチで実施する作業**:

- [ ] T032 ブランチ作成: `git checkout -b 007-backtest-engine`
- [ ] T033 このブランチ専用のspec作成（User Story 1の詳細化）
- [ ] T034 このブランチ専用のtasks.md生成
- [ ] T035 TDD実装（以下を含む）
  - src/qeel/schemas/validators.py: PortfolioSchema追加（必須列: datetime, symbol; オプション列は検証スキップ）
  - src/qeel/engines/base.py: BaseEngine（共通フロー、Template Methodパターン）
  - src/qeel/engines/backtest.py: BacktestEngine
  - iteration管理ロジック
  - 取引日判定ロジック（toml設定のtradingCalendarを使用）
  - src/qeel/portfolio_constructors/base.py: BasePortfolioConstructor ABC（戻り値を`pl.DataFrame`）
  - src/qeel/portfolio_constructors/top_n.py: TopNPortfolioConstructor（デフォルト実装、signal_strengthをメタデータとして返す）
  - src/qeel/order_creators/base.py: BaseOrderCreator ABC（引数`portfolio_df: pl.DataFrame`に変更）
  - src/qeel/order_creators/equal_weight.py: EqualWeightOrderCreator（デフォルト実装、メタデータ活用）
  - tests/unit/test_engines.py
  - tests/unit/test_portfolio_constructors.py（新インターフェースに対応）
  - tests/unit/test_order_creators.py（新インターフェースに対応）
  - tests/contract/test_portfolio_constructor_contract.py（戻り値がDataFrameであることを検証）
  - tests/contract/test_order_creator_contract.py（引数がDataFrameであることを検証）
  - tests/integration/test_backtest_e2e.py
- [ ] T036 User Story 1のAcceptance Scenariosをすべて満たすことを確認
- [ ] T037 PRを作成しマージ

**完了条件**:
- E2Eでバックテストが実行される
- Acceptance Scenarios 1-3がすべてパス
- シャープレシオ、最大ドローダウンなどの指標が算出される

---

#### Branch 008: パフォーマンス指標計算

**Branch Name**: `008-metrics-calculation`
**目的**: パフォーマンス指標計算機能の追加
**依存**: `007-backtest-engine`
**User Story**: User Story 1（結果検証）の完成

**このブランチで実施する作業**:

- [ ] T038 ブランチ作成: `git checkout -b 008-metrics-calculation`
- [ ] T039 このブランチ専用のtasks.md生成
- [ ] T040 TDD実装（以下を含む）
  - src/qeel/metrics/calculator.py: メトリクス計算ロジック
  - シャープレシオ、最大ドローダウン、勝率等
  - tests/unit/test_metrics.py
- [ ] T041 PRを作成しマージ

**完了条件**:
- 約定データから正しく指標が算出される
- Polarsの効率的なagg操作が活用されている

---

### Phase 2.3: User Story 2（P2）- 実運用への転用

#### Branch 009: 実運用エンジン

**Branch Name**: `009-live-engine`
**目的**: 実運用エンジン実装（P2完成）
**依存**: `007-backtest-engine`
**User Story**: **User Story 2（P2）**

**このブランチで実施する作業**:

- [ ] T042 ブランチ作成: `git checkout -b 009-live-engine`
- [ ] T043 このブランチ専用のspec作成（User Story 2の詳細化）
- [ ] T044 このブランチ専用のtasks.md生成
- [ ] T045 TDD実装（以下を含む）
  - src/qeel/engines/live.py: LiveEngine
  - バックテストとの再現性保証ロジック
  - 当日iteration実行機能
  - tests/integration/test_live_e2e.py
- [ ] T046 同一日時・データで BacktestEngine と LiveEngine が同じOrdersを生成することを確認
- [ ] T047 PRを作成しマージ

**完了条件**:
- User Story 2のAcceptance Scenarios 1-3がすべてパス
- バックテストと実運用で注文内容が100%一致

---

#### Branch 010: 実運用Executor実装例

**Branch Name**: `010-executor-examples`
**目的**: 実運用用Executor実装例とドキュメント
**依存**: `009-live-engine`
**User Story**: User Story 2（API連携）

**このブランチで実施する作業**:

- [ ] T048 ブランチ作成: `git checkout -b 010-executor-examples`
- [ ] T049 このブランチ専用のtasks.md生成
- [ ] T050 実装（以下を含む）
  - src/qeel/executors/examples/exchange_api.py: 取引所API実装例（スケルトン）
  - ユーザ向けドキュメント
  - tests/unit/test_executor_examples.py（モックAPIクライアントで動作確認）
- [ ] T051 PRを作成しマージ

**完了条件**:
- ユーザが独自のExecutorを実装できるガイドが整備
- サンプルコードが動作

---

### Phase 2.4: User Story 3（P3-1）- シグナル分析の分布評価

#### Branch 011: リターン計算ABC

**Branch Name**: `011-return-calculator-abc`
**目的**: リターン計算ABCとサンプル実装
**依存**: `002-core-config-and-schemas`
**User Story**: User Story 3（リターン計算）

**このブランチで実施する作業**:

- [ ] T052 ブランチ作成: `git checkout -b 011-return-calculator-abc`
- [ ] T053 このブランチ専用のtasks.md生成
- [ ] T054 TDD実装（以下を含む）
  - src/qeel/calculators/returns/base.py: BaseReturnCalculator ABC
  - src/qeel/calculators/returns/examples/log_return.py: 対数リターン実装例
  - tests/unit/test_return_calculator.py
  - tests/contract/test_return_calculator_contract.py
- [ ] T055 PRを作成しマージ

**完了条件**:
- モックデータでリターン計算が正しく動作

---

#### Branch 012: シグナル分析機能

**Branch Name**: `012-signal-analysis`
**目的**: シグナル分析機能実装（P3-1完成）
**依存**: `004-calculator-abc`, `011-return-calculator-abc`
**User Story**: **User Story 3（P3）**

**このブランチで実施する作業**:

- [ ] T056 ブランチ作成: `git checkout -b 012-signal-analysis`
- [ ] T057 このブランチ専用のspec作成（User Story 3の詳細化）
- [ ] T058 このブランチ専用のtasks.md生成
- [ ] T059 TDD実装（以下を含む）
  - src/qeel/analysis/rank_correlation.py: 順位相関係数計算
  - src/qeel/analysis/visualizer.py: 分布可視化
  - パラメータグリッド評価機能
  - tests/unit/test_analysis.py
  - tests/integration/test_signal_analysis_e2e.py
- [ ] T060 User Story 3のAcceptance Scenarios 1-3がすべてパス
- [ ] T061 PRを作成しマージ

**完了条件**:
- シグナルとリターンから順位相関が計算される
- 年次・パラメータ別の分布が可視化される

---

### Phase 2.5: User Story 4（P3-2）- バックテストと実運用の差異検証

#### Branch 013: バックテストと実運用の差異分析

**Branch Name**: `013-backtest-live-divergence`
**目的**: バックテストと実運用の差異検証機能実装（P3-2完成）
**依存**: `008-metrics-calculation`, `009-live-engine`
**User Story**: **User Story 4（P3）**

**このブランチで実施する作業**:

- [ ] T062 ブランチ作成: `git checkout -b 013-backtest-live-divergence`
- [ ] T063 このブランチ専用のspec作成（User Story 4の詳細化）
- [ ] T064 このブランチ専用のtasks.md生成
- [ ] T065 TDD実装（以下を含む）
  - src/qeel/diagnostics/comparison.py: バックテストと実運用の差異計算ロジック
  - src/qeel/diagnostics/visualizer.py: 差異可視化
  - 詳細ログ出力機能
  - tests/unit/test_diagnostics.py
  - tests/integration/test_backtest_live_divergence_e2e.py
- [ ] T066 User Story 4のAcceptance Scenarios 1-2がすべてパス
- [ ] T067 PRを作成しマージ

**完了条件**:
- バックテストと実運用の約定データから差異が可視化される
- 差異の原因が特定できる情報が提供される

---

## Phase 3: ポリッシュと最終統合

### Branch 014: ドキュメント整備とパッケージング

**Branch Name**: `014-documentation-and-packaging`
**目的**: ユーザ向けドキュメント整備、PyPIパッケージング準備
**依存**: すべての機能ブランチ完了後
**User Story**: N/A（ポリッシュ）

**このブランチで実施する作業**:

- [ ] T068 ブランチ作成: `git checkout -b 014-documentation-and-packaging`
- [ ] T069 README.md作成（インストール方法、基本的な使い方）
- [ ] T070 API Referenceドキュメント生成（sphinx等）
- [ ] T071 pyproject.tomlのメタデータ整備
- [ ] T072 LICENSE、CONTRIBUTING.md作成
- [ ] T073 パッケージビルドテスト
- [ ] T074 PRを作成しマージ

**完了条件**:
- ユーザが `pip install qeel` でインストール可能
- ドキュメントが完備

---

## 依存関係グラフ

```
Phase 1: 基盤構築
  002 (Config & Schemas)
   ├─→ 002a (Utils - retry, notification)
   ├─→ 003 (DataSource ABC)
   ├─→ 004 (Calculator ABC)
   ├─→ 005 (Context Management)
   └─→ 006 (Executor ABC)

Phase 2: P1完成（バックテスト）
  003, 004, 005, 006 → 007 (Backtest Engine) → 008 (Metrics)

Phase 3: P2完成（実運用）
  007 → 009 (Live Engine) → 010 (Executor Examples)
  002a → 010 (Executor Examples - utils使用)

Phase 4: P3-1完成（シグナル分析）
  002 → 011 (Return Calculator ABC)
  004, 011 → 012 (Signal Analysis)

Phase 5: P3-2完成（差異検証）
  008, 009 → 013 (Backtest-Live Divergence)

Phase 6: ポリッシュ
  全機能完了 → 014 (Documentation & Packaging)
```

---

## 並列実行可能なブランチ

以下のブランチは依存関係がないため、並列で作業可能：

**Phase 1（基盤構築）**:
- 002完了後: 002a, 003, 004, 005, 006を並列実行可能

**Phase 4-5（P3機能）**:
- 011と013は独立して並列実行可能

---

## マイルストーン

- **M1（基盤完成）**: Branch 002-006（002a含む）完了 → 基盤クラスがすべて揃う
- **M2（MVP完成、P1）**: Branch 007-008完了 → **バックテスト機能が動作し、ユーザに価値提供可能**
- **M3（P2完成）**: Branch 009-010完了 → 実運用機能が動作（utilsヘルパー利用可能）
- **M4（P3完成）**: Branch 011-013完了 → 分析機能が完成
- **M5（リリース準備完了）**: Branch 014完了 → PyPIリリース可能

---

## MVP（最小限の価値提供）スコープ

**推奨MVPスコープ**: M2（P1完成）

- Branch 002-008まで完了
- バックテスト機能が動作
- ユーザはシグナル計算ロジックを実装してバックテストを実行できる
- パフォーマンス指標が算出される

このMVPで、クオンツアナリストがバックテストを実行し、戦略の有効性を検証できる。

---

## 実装戦略

1. **段階的デリバリー**: M1 → M2（MVP）→ M3 → M4 → M5の順で段階的にデリバリー
2. **独立したブランチ**: 各ブランチは独立してテスト・マージ可能
3. **TDD厳守**: すべてのブランチでRed-Green-Refactorサイクルを適用
4. **継続的統合**: 各ブランチマージ後、E2Eテストで全体の整合性を確認

---

## 次のアクション

1. このtasks.mdをコミット
2. Branch 002（`002-core-config-and-schemas`）を作成
3. Branch 002で `/speckit.tasks` を実行し、詳細な実装タスクを生成
4. TDD実装を開始

---

**総タスク数**: 79タスク（このブランチ: 9、機能ブランチ作成・実装: 70）
**機能ブランチ数**: 14ブランチ（002, 002a, 003-014）
**User Story完成順序**: P1（M2）→ P2（M3）→ P3（M4）
