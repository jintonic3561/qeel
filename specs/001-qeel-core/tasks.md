# Tasks: Qeel - 量的トレーディング向けバックテストライブラリ

**Input**: 設計ドキュメント from `/specs/001-qeel-core/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: タスクはplan.mdで提案されたブランチ構造(002-014)に基づき整理される。各ブランチは独立したフェーズとして実装可能であり、段階的な機能追加を可能にする。

**Note**: 本ブランチ(`001-qeel-core`)では実装は行わない。このtasks.mdは各ブランチで何を実装すべきかを示すロードマップとして機能する。

---

## Format: `[ID] Description`

- タスクIDは通し番号で管理(T001, T002, T003...)
- 各ブランチの実装範囲を明確化し、ブランチ作成時に参照可能にする
- ファイルパスは`src/qeel/`配下の絶対パスで記述

---

## Phase 1: Branch 002 - Core Config and Schemas

**Branch**: `002-core-config-and-schemas`
**Purpose**: 設定管理とスキーマバリデーションの基盤を構築する。toml設定ファイルの厳密なバリデーションと型安全性を確保。
**Dependencies**: なし
**User Story**: N/A（基盤）

### 実装タスク

- [ ] T001 プロジェクト構造の作成（src/qeel/, tests/, pyproject.toml, mypy.ini）
- [ ] T002 pyproject.tomlの設定（依存関係: polars, pydantic, tomli, boto3）
- [ ] T003 mypy.iniのstrict設定（strictモード、型チェック厳格化）
- [ ] T004 src/qeel/config/models.pyにDataSourceConfigを実装（Pydantic、バリデーション付き）
- [ ] T005 src/qeel/config/models.pyにCostConfigを実装（手数料・スリッページモデルのバリデーション）
- [ ] T006 src/qeel/config/models.pyにMethodTimingConfigを実装（各メソッドの実行タイミング設定）
- [ ] T007 src/qeel/config/models.pyにLoopConfigを実装（バックテスト期間・頻度・ユニバース設定）
- [ ] T008 src/qeel/config/models.pyにGeneralConfigを実装（storage_type、S3設定のバリデーション）
- [ ] T009 src/qeel/config/models.pyにConfigを実装（from_toml()メソッド、全体設定統合）
- [ ] T010 src/qeel/schemas/validators.pyにOHLCVSchemaを実装（必須列のバリデーション）
- [ ] T011 src/qeel/schemas/validators.pyにSignalSchemaを実装（datetime, symbol必須、シグナル列は任意）
- [ ] T012 src/qeel/schemas/validators.pyにPortfolioSchemaを実装（datetime, symbol必須、メタデータ列は任意）
- [ ] T013 src/qeel/schemas/validators.pyにPositionSchemaを実装（symbol, quantity, avg_price必須）
- [ ] T014 src/qeel/schemas/validators.pyにOrderSchemaを実装（side, quantity, price, order_typeバリデーション）
- [ ] T015 src/qeel/schemas/validators.pyにFillReportSchemaを実装（約定情報のバリデーション）
- [ ] T016 src/qeel/schemas/validators.pyにReturnSchemaを実装（リターン計算結果のバリデーション）
- [ ] T017 tests/unit/test_config.pyに設定バリデーションテスト（不正tomlでValidationError）
- [ ] T018 tests/unit/test_schemas.pyにスキーマバリデーションテスト（不正DataFrameでValueError）
- [ ] T019 ruffとmypyの実行確認（ruff check、mypy src/qeel）

**Checkpoint**: 設定とスキーマバリデーションの基盤が完成し、型安全性が確保される

---

## Phase 2: Branch 003 - Utils Infrastructure

**Branch**: `003-utils-infrastructure`
**Purpose**: 実運用Executor実装を支援するユーティリティ群を提供。APIリトライ、通知、丸め処理など。
**Dependencies**: 002-core-config-and-schemas
**User Story**: User Story 2（実運用支援、オプション機能）

### 実装タスク

- [ ] T020 src/qeel/utils/retry.pyにwith_retry()を実装（exponential backoff、タイムアウト、リトライロジック）
- [ ] T021 src/qeel/utils/notification.pyにsend_slack_notification()を実装（Slack Webhook経由のエラー通知）
- [ ] T022 src/qeel/utils/rounding.pyにround_to_unit()を実装（数量・価格の丸め処理、取引所仕様対応）
- [ ] T023 src/qeel/utils/__init__.pyにget_workspace()を実装（環境変数QEEL_WORKSPACEまたはカレントディレクトリ）
- [ ] T024 tests/unit/test_retry.pyにリトライロジックのテスト（モックAPIクライアント、backoff確認）
- [ ] T025 tests/unit/test_notification.pyに通知送信のテスト（モックWebhook、ペイロード確認）
- [ ] T026 tests/unit/test_rounding.pyに丸め処理のテスト（精度検証、境界値テスト）
- [ ] T027 tests/unit/test_utils.pyにget_workspace()のテスト（環境変数設定・未設定の両方）

**Checkpoint**: ユーザが実運用Executor実装時に自由に利用可能なユーティリティが揃う

---

## Phase 3: Branch 004 - Data Source ABC

**Branch**: `004-data-source-abc`
**Purpose**: データソースABCと共通ヘルパーメソッド、テスト用MockDataSourceを実装。
**Dependencies**: 002-core-config-and-schemas
**User Story**: N/A（基盤、User Story 1で使用）

### 実装タスク

- [ ] T028 src/qeel/data_sources/base.pyにBaseDataSourceを実装（ABCパターン、fetch()抽象メソッド）
- [ ] T029 BaseDataSourceに_normalize_datetime_column()ヘルパーを実装（datetime列正規化）
- [ ] T030 BaseDataSourceに_adjust_window_for_offset()ヘルパーを実装（offset_secondsによるwindow調整）
- [ ] T031 BaseDataSourceに_filter_by_datetime_and_symbols()ヘルパーを実装（datetime範囲・銘柄フィルタリング）
- [ ] T032 src/qeel/data_sources/mock.pyにMockDataSourceを実装（テスト用、ヘルパーメソッド使用例）
- [ ] T033 tests/unit/test_data_sources.pyにMockDataSource.fetch()のテスト（フィルタリング動作確認）
- [ ] T034 tests/unit/test_data_sources.pyにヘルパーメソッドの単体テスト（正規化、window調整、フィルタリング）
- [ ] T035 tests/contract/test_data_source_contract.pyにBaseDataSource契約テスト（サブクラスがfetch()実装を強制されることを確認）

**Checkpoint**: データソース基盤が完成し、ユーザは独自データソースを実装可能

---

## Phase 4: Branch 005 - Calculator ABC

**Branch**: `005-calculator-abc`
**Purpose**: シグナル計算ABCとサンプル実装（移動平均クロス）を提供。
**Dependencies**: 002-core-config-and-schemas
**User Story**: User Story 1（シグナル計算）

### 実装タスク

- [ ] T036 src/qeel/calculators/signals/base.pyにBaseSignalCalculatorを実装（ABCパターン、calculate()抽象メソッド）
- [ ] T037 BaseSignalCalculatorに_validate_output()ヘルパーを実装（SignalSchemaバリデーション）
- [ ] T038 src/qeel/calculators/signals/examples/moving_average.pyにMovingAverageCrossParamsを実装（Pydanticモデル）
- [ ] T039 src/qeel/calculators/signals/examples/moving_average.pyにMovingAverageCrossCalculatorを実装（サンプル戦略）
- [ ] T040 tests/unit/test_calculators.pyにMovingAverageCrossCalculator.calculate()のテスト（モックデータで正しくシグナル計算）
- [ ] T041 tests/unit/test_calculators.pyに_validate_output()ヘルパーのテスト（不正スキーマでValueError）
- [ ] T042 tests/contract/test_signal_calculator_contract.pyにBaseSignalCalculator契約テスト（サブクラスがcalculate()実装を強制されることを確認）

**Checkpoint**: シグナル計算基盤が完成し、ユーザは独自シグナル計算ロジックを実装可能

---

## Phase 5: Branch 006 - IO and Context Management

**Branch**: `006-io-and-context-management`
**Purpose**: IOレイヤー（Local/S3）とコンテキスト管理の実装。トレーサビリティと永続化を確保。
**Dependencies**: 002-core-config-and-schemas
**User Story**: User Story 1（コンテキスト永続化）、User Story 2（実運用でS3使用）

### 実装タスク

- [ ] T043 src/qeel/models/context.pyにContextを実装（Pydanticモデル、DataFrameフィールド、arbitrary_types_allowed）
- [ ] T044 src/qeel/io/base.pyにBaseIOを実装（ABCパターン、from_config()ファクトリメソッド）
- [ ] T045 BaseIOに抽象メソッドget_base_path()、get_partition_dir()、save()、load()、exists()を定義
- [ ] T046 src/qeel/io/local.pyにLocalIOを実装（ワークスペース配下のファイル操作、年月パーティショニング）
- [ ] T047 src/qeel/io/s3.pyにS3IOを実装（S3クライアント経由のオブジェクト操作、年月パーティショニング）
- [ ] T048 src/qeel/stores/context_store.pyにContextStoreを実装（IOレイヤー依存、signals/portfolio_plan/ordersを個別保存）
- [ ] T049 ContextStoreにsave_signals()、save_portfolio_plan()、save_orders()を実装（日付パーティショニング）
- [ ] T050 ContextStoreにload()を実装（指定日付の各要素を復元、current_positionsはExchangeClientから取得）
- [ ] T051 ContextStoreにload_latest()を実装（最新日付のコンテキストを復元）
- [ ] T052 ContextStoreにexists()を実装（指定日付のコンテキスト存在確認）
- [ ] T053 src/qeel/stores/in_memory.pyにInMemoryStoreを実装（テスト用、最新のみ保持）
- [ ] T054 tests/unit/test_io.pyにLocalIO.save()/load()/exists()のテスト（json/parquet対応確認）
- [ ] T055 tests/unit/test_io.pyにS3IO.save()/load()/exists()のテスト（モックboto3で動作確認）
- [ ] T056 tests/unit/test_io.pyにBaseIO.from_config()のテスト（storage_typeに応じた実装返却確認）
- [ ] T057 tests/unit/test_stores.pyにContextStore.save_*()のテスト（IOレイヤー経由で保存確認）
- [ ] T058 tests/unit/test_stores.pyにContextStore.load()/load_latest()/exists()のテスト（復元確認）
- [ ] T059 tests/unit/test_stores.pyにInMemoryStoreのテスト（最新コンテキスト保持確認）

**Checkpoint**: IOレイヤーとコンテキスト管理が完成し、トレーサビリティが確保される

---

## Phase 6: Branch 007 - Exchange Client and Mock

**Branch**: `007-exchange-client-and-mock`
**Purpose**: 取引所クライアントABCとモック約定・ポジション管理を実装。
**Dependencies**: 002-core-config-and-schemas
**User Story**: User Story 1（約定シミュレーション）

### 実装タスク

- [ ] T060 src/qeel/exchange_clients/base.pyにBaseExchangeClientを実装（ABCパターン、submit_orders()、fetch_fills()、fetch_positions()抽象メソッド）
- [ ] T061 BaseExchangeClientに_validate_orders()、_validate_fills()、_validate_positions()ヘルパーを実装（スキーマバリデーション）
- [ ] T062 src/qeel/exchange_clients/mock.pyにMockExchangeClientを実装（バックテスト用、即座に約定処理）
- [ ] T063 MockExchangeClientにコスト計算ロジックを実装（手数料、スリッページ、マーケットインパクト）
- [ ] T064 MockExchangeClient.fetch_positions()を実装（約定履歴から現在のポジション計算）
- [ ] T065 tests/unit/test_executors.pyにMockExchangeClient.submit_orders()のテスト（即座に約定生成確認）
- [ ] T066 tests/unit/test_executors.pyにMockExchangeClient.fetch_fills()のテスト（コスト反映確認）
- [ ] T067 tests/unit/test_executors.pyにMockExchangeClient.fetch_positions()のテスト（ポジション計算確認）
- [ ] T068 tests/contract/test_executor_contract.pyにBaseExchangeClient契約テスト（サブクラスが抽象メソッド実装を強制されることを確認）

**Checkpoint**: モック約定とポジション管理が完成し、バックテスト基盤が整う

---

## Phase 7: Branch 008 - Backtest Engine

**Branch**: `008-backtest-engine`
**Purpose**: バックテストエンジン本体を実装し、User Story 1（P1）を完成させる。
**Dependencies**: 004-data-source-abc, 005-calculator-abc, 006-io-and-context-management, 007-exchange-client-and-mock
**User Story**: User Story 1（P1、バックテスト実行と結果検証）

### 実装タスク

- [ ] T069 src/qeel/engines/base.pyにBaseEngineを実装（Template Methodパターン、共通フロー定義）
- [ ] T070 BaseEngineにrun_iteration()を実装（データ取得→シグナル計算→ポートフォリオ構築→注文生成→執行の共通フロー）
- [ ] T071 BaseEngineに_execute_orders()抽象メソッドを定義（サブクラスで実装）
- [ ] T072 BaseEngineに取引日判定ロジックを実装（toml設定のtradingCalendarを使用）
- [ ] T073 BaseEngineにユニバース管理ロジックを実装（LoopConfig.universeをBaseDataSource.fetch()に渡す）
- [ ] T074 src/qeel/portfolio_constructors/base.pyにBasePortfolioConstructorを実装（ABCパターン、construct()抽象メソッド）
- [ ] T075 BasePortfolioConstructorに_validate_inputs()、_validate_output()ヘルパーを実装（スキーマバリデーション）
- [ ] T076 src/qeel/portfolio_constructors/top_n.pyにTopNConstructorParamsを実装（Pydanticモデル、top_n, ascending）
- [ ] T077 src/qeel/portfolio_constructors/top_n.pyにTopNPortfolioConstructorを実装（デフォルト実装、シグナル上位N銘柄選定+メタデータ付与）
- [ ] T078 src/qeel/order_creators/base.pyにBaseOrderCreatorを実装（ABCパターン、create()抽象メソッド）
- [ ] T079 BaseOrderCreatorに_validate_inputs()ヘルパーを実装（portfolio_plan, current_positions, ohlcvのスキーマバリデーション）
- [ ] T080 src/qeel/order_creators/equal_weight.pyにEqualWeightParamsを実装（Pydanticモデル、capital, rebalance_threshold）
- [ ] T081 src/qeel/order_creators/equal_weight.pyにEqualWeightOrderCreatorを実装（デフォルト実装、等ウェイト注文生成、メタデータ活用）
- [ ] T082 src/qeel/engines/backtest.pyにBacktestEngineを実装（BaseEngineを継承、_execute_orders()でモック約定）
- [ ] T083 BacktestEngine.run()を実装（ループ管理、iteration実行、fill_history集約）
- [ ] T084 tests/unit/test_engines.pyにBacktestEngine.run_iteration()のテスト（モックデータで1iteration実行確認）
- [ ] T085 tests/unit/test_engines.pyにユニバース管理のテスト（LoopConfig.universe指定時の銘柄フィルタリング確認）
- [ ] T086 tests/unit/test_portfolio_constructors.pyにTopNPortfolioConstructor.construct()のテスト（上位N選定+メタデータ確認）
- [ ] T087 tests/unit/test_order_creators.pyにEqualWeightOrderCreator.create()のテスト（等ウェイト注文生成確認）
- [ ] T088 tests/integration/test_backtest_e2e.pyにE2Eバックテストテスト（User Story 1のAcceptance Scenarios検証）
- [ ] T089 tests/contract/test_portfolio_constructor_contract.pyにBasePortfolioConstructor契約テスト
- [ ] T090 tests/contract/test_order_creator_contract.pyにBaseOrderCreator契約テスト

**Checkpoint**: User Story 1（P1）完成 - バックテスト機能が動作し、パフォーマンス指標算出可能

---

## Phase 8: Branch 009 - Metrics Calculation

**Branch**: `009-metrics-calculation`
**Purpose**: パフォーマンス指標計算を実装し、User Story 1を完全に完成させる。
**Dependencies**: 008-backtest-engine
**User Story**: User Story 1（結果検証）

### 実装タスク

- [ ] T091 src/qeel/metrics/calculator.pyにcalculate_metrics()を実装（Polars lazy APIで日次リターン→累積リターン→シャープレシオ→最大ドローダウン計算）
- [ ] T092 calculate_metrics()にシャープレシオ計算を実装（平均リターン/ボラティリティ）
- [ ] T093 calculate_metrics()に最大ドローダウン計算を実装（累積リターンの最大下落幅）
- [ ] T094 calculate_metrics()に勝率計算を実装（正のリターンの割合）
- [ ] T095 tests/unit/test_metrics.pyにcalculate_metrics()のテスト（モック約定データから正しく指標算出確認）
- [ ] T096 tests/unit/test_metrics.pyにシャープレシオのテスト（既知データで計算精度検証）
- [ ] T097 tests/unit/test_metrics.pyに最大ドローダウンのテスト（既知データで計算精度検証）
- [ ] T098 tests/integration/test_backtest_e2e.pyにメトリクス計算の統合テスト（E2Eでメトリクス算出確認）

**Checkpoint**: User Story 1完全完成 - バックテスト結果の検証が可能

---

## Phase 9: Branch 010 - Live Engine

**Branch**: `010-live-engine`
**Purpose**: 実運用エンジンを実装し、User Story 2（P2）を完成させる。
**Dependencies**: 008-backtest-engine
**User Story**: User Story 2（P2、実運用への転用）

### 実装タスク

- [ ] T099 src/qeel/engines/live.pyにLiveEngineを実装（BaseEngineを継承、_execute_orders()で実API呼び出し）
- [ ] T100 LiveEngine.run_iteration()を実装（当日を指定して単一iteration実行）
- [ ] T101 LiveEngineにバックテストとの再現性保証ロジックを実装（同一日時・データで同じOrdersを生成）
- [ ] T102 tests/unit/test_engines.pyにLiveEngine.run_iteration()のテスト（モックExchangeClientで動作確認）
- [ ] T103 tests/integration/test_live_e2e.pyにE2E実運用テスト（User Story 2のAcceptance Scenarios検証）
- [ ] T104 tests/integration/test_live_e2e.pyにバックテスト・実運用再現性テスト（同一日時で同じOrders生成確認）

**Checkpoint**: User Story 2（P2）完成 - 実運用機能が動作し、バックテストと同一コードで運用可能

---

## Phase 10: Branch 011 - Executor Examples

**Branch**: `011-executor-examples`
**Purpose**: 実運用用Executor実装例（スケルトン）を提供し、User Story 2を完全に完成させる。
**Dependencies**: 010-live-engine, 003-utils-infrastructure
**User Story**: User Story 2（API連携）

### 実装タスク

- [ ] T105 src/qeel/exchange_clients/examples/exchange_api.pyにExchangeAPIClientを実装（スケルトン、qeel.utils使用例）
- [ ] T106 ExchangeAPIClient.submit_orders()を実装（with_retry、send_slack_notification、round_to_unit使用例）
- [ ] T107 ExchangeAPIClient.fetch_fills()を実装（with_retry、APIから約定情報取得）
- [ ] T108 ExchangeAPIClient.fetch_positions()を実装（with_retry、APIからポジション取得）
- [ ] T109 tests/unit/test_executors.pyにExchangeAPIClientのテスト（モックAPIクライアントで動作確認）
- [ ] T110 tests/unit/test_executors.pyにリトライロジックのテスト（API失敗時のbackoff確認）
- [ ] T111 tests/unit/test_executors.pyに通知送信のテスト（エラー時のSlack通知確認）

**Checkpoint**: User Story 2完全完成 - 実運用Executor実装例が揃い、ユーザは参考にして独自実装可能

---

## Phase 11: Branch 012 - Return Calculator ABC

**Branch**: `012-return-calculator-abc`
**Purpose**: リターン計算ABCとサンプル実装（対数リターン）を提供。
**Dependencies**: 002-core-config-and-schemas
**User Story**: User Story 3（リターン計算）

### 実装タスク

- [ ] T112 src/qeel/calculators/returns/base.pyにBaseReturnCalculatorを実装（ABCパターン、calculate()抽象メソッド）
- [ ] T113 BaseReturnCalculatorに_validate_output()ヘルパーを実装（ReturnSchemaバリデーション）
- [ ] T114 src/qeel/calculators/returns/examples/log_return.pyにLogReturnParamsを実装（Pydanticモデル、period）
- [ ] T115 src/qeel/calculators/returns/examples/log_return.pyにLogReturnCalculatorを実装（前向きリターン計算、リーク防止）
- [ ] T116 tests/unit/test_calculators.pyにLogReturnCalculator.calculate()のテスト（forward return確認、リーク防止検証）
- [ ] T117 tests/unit/test_calculators.pyに_validate_output()ヘルパーのテスト（不正スキーマでValueError）
- [ ] T118 tests/contract/test_return_calculator_contract.pyにBaseReturnCalculator契約テスト（サブクラスがcalculate()実装を強制されることを確認）

**Checkpoint**: リターン計算基盤が完成し、ユーザは独自リターン計算ロジックを実装可能

---

## Phase 12: Branch 013 - Signal Analysis

**Branch**: `013-signal-analysis`
**Purpose**: シグナル分析機能を実装し、User Story 3（P3）を完成させる。
**Dependencies**: 005-calculator-abc, 012-return-calculator-abc
**User Story**: User Story 3（P3、シグナル評価の分布評価）

### 実装タスク

- [ ] T119 src/qeel/analysis/rank_correlation.pyにcalculate_rank_correlation()を実装（シグナルとリターンの順位相関係数計算）
- [ ] T120 calculate_rank_correlation()に年次別・パラメータ別の分布計算を実装
- [ ] T121 src/qeel/analysis/visualizer.pyにplot_rank_correlation_distribution()を実装（分布可視化）
- [ ] T122 src/qeel/analysis/grid_evaluation.pyにevaluate_parameter_grid()を実装（複数パラメータ組の順位相関計算）
- [ ] T123 tests/unit/test_analysis.pyにcalculate_rank_correlation()のテスト（既知データで計算精度検証）
- [ ] T124 tests/unit/test_analysis.pyにplot_rank_correlation_distribution()のテスト（可視化出力確認）
- [ ] T125 tests/unit/test_analysis.pyにevaluate_parameter_grid()のテスト（グリッド評価確認）
- [ ] T126 tests/integration/test_signal_analysis_e2e.pyにE2Eシグナル分析テスト（User Story 3のAcceptance Scenarios検証）

**Checkpoint**: User Story 3（P3）完成 - シグナル分析機能が動作し、パラメータ評価が可能

---

## Phase 13: Branch 014 - Backtest-Live Divergence

**Branch**: `014-backtest-live-divergence`
**Purpose**: バックテストと実運用の差異検証を実装し、User Story 4（P3）を完成させる。
**Dependencies**: 009-metrics-calculation, 010-live-engine
**User Story**: User Story 4（P3、バックテストと実運用の乖離検証）

### 実装タスク

- [ ] T127 src/qeel/diagnostics/comparison.pyにcompare_backtest_live()を実装（バックテストと実運用の差異計算）
- [ ] T128 compare_backtest_live()に日次リターン差分計算を実装
- [ ] T129 compare_backtest_live()に累積リターン差分計算を実装
- [ ] T130 src/qeel/diagnostics/visualizer.pyにplot_divergence()を実装（差異可視化）
- [ ] T131 src/qeel/diagnostics/logger.pyにlog_divergence_details()を実装（詳細ログ出力、乖離原因特定情報）
- [ ] T132 tests/unit/test_diagnostics.pyにcompare_backtest_live()のテスト（差異計算確認）
- [ ] T133 tests/unit/test_diagnostics.pyにplot_divergence()のテスト（可視化出力確認）
- [ ] T134 tests/unit/test_diagnostics.pyにlog_divergence_details()のテスト（詳細ログ確認）
- [ ] T135 tests/integration/test_backtest_live_divergence_e2e.pyにE2E差異検証テスト（User Story 4のAcceptance Scenarios検証）

**Checkpoint**: User Story 4（P3）完成 - バックテストと実運用の乖離検証が可能

---

## Phase 14: Polish & Cross-Cutting Concerns

**Branch**: 完成後に個別ブランチまたはメインブランチで実施
**Purpose**: プロジェクト全体の品質向上と横断的な改善
**Dependencies**: すべてのUser Storyが完成

### 実装タスク

- [ ] T136 README.mdの更新（インストール手順、クイックスタート、ドキュメントリンク）
- [ ] T137 quickstart.mdの検証（実際に実行して動作確認）
- [ ] T138 型ヒント完全性の確認（mypy strictモードでゼロエラー）
- [ ] T139 ruffによるコードスタイル統一（ruff format実行）
- [ ] T140 docstringの日本語化完全性確認（すべての公開APIに日本語docstring）
- [ ] T141 qeel initコマンドの実装（ワークスペース初期化、テンプレート生成）
- [ ] T142 ParquetDataSourceの標準実装（src/qeel/data_sources/parquet.py、IOレイヤー使用、ヘルパーメソッド活用）
- [ ] T143 tests/unit/test_data_sources.pyにParquetDataSource.fetch()のテスト
- [ ] T144 エラーメッセージの日本語化確認（すべてのValidationErrorが日本語）
- [ ] T145 パフォーマンス最適化（Polars lazy APIの活用確認）
- [ ] T146 セキュリティ監査（credentials漏洩防止、入力バリデーション確認）

**Checkpoint**: プロジェクト全体が完成し、すべての憲章原則に準拠

---

## Dependencies & Execution Order

### Branch Dependencies

```
002 (Config & Schemas) - 基盤、すべてのブランチの依存元
 ├─ 003 (Utils) - 実運用支援ユーティリティ
 ├─ 004 (DataSource ABC) - データソース基盤
 ├─ 005 (Calculator ABC) - シグナル計算基盤
 └─ 006 (IO & Context) - IOレイヤーとコンテキスト管理

004 + 005 + 006 + 007 (ExchangeClient) → 008 (Backtest Engine) - P1完成
008 → 009 (Metrics) - User Story 1完全完成
008 → 010 (Live Engine) - P2実装
010 + 003 → 011 (Executor Examples) - User Story 2完全完成

005 + 012 (Return Calculator) → 013 (Signal Analysis) - User Story 3完成
009 + 010 → 014 (Divergence) - User Story 4完成
```

### Recommended Implementation Order

1. **基盤構築**: 002 → 003 → 004 → 005 → 006 → 007（すべてのブランチの土台）
2. **P1完成（MVP）**: 008 → 009（バックテスト機能完成）
3. **P2完成**: 010 → 011（実運用機能完成）
4. **P3完成**: 012 → 013（シグナル分析）、014（差異検証）
5. **仕上げ**: Polish & Cross-Cutting Concerns

### Parallel Opportunities

- **003 (Utils)** と **004 (DataSource)** は並行実装可能（依存なし、002完了後）
- **005 (Calculator)** と **006 (IO & Context)** は並行実装可能（依存なし、002完了後）
- **013 (Signal Analysis)** と **014 (Divergence)** は並行実装可能（依存なし、009, 010, 012完了後）

---

## Branch Implementation Strategy

### 各ブランチでの作業手順

1. ブランチ作成: `git checkout -b <branch-name>`
2. そのブランチ専用の仕様書作成: `/speckit.specify`（必要に応じて）
3. 実装計画: `/speckit.plan`（このplan.mdを参照）
4. タスク生成: `/speckit.tasks`（このtasks.mdを参照し、そのブランチのタスクを抽出）
5. TDDで実装: `/speckit.implement`
6. テスト完了後、PRを作成しマージ

### Milestones

- **M1（基盤完成）**: Branch 002-007完了 → 基盤クラスがすべて揃う
- **M2（P1完成）**: Branch 008-009完了 → バックテスト機能が動作
- **M3（P2完成）**: Branch 010-011完了 → 実運用機能が動作
- **M4（P3完成）**: Branch 012-014完了 → 分析機能が完成

---

## Notes

- 各ブランチは独立したPRとしてマージ可能（段階的統合）
- TDD厳守（Red-Green-Refactorサイクル）
- 型ヒント必須（mypy strictモード）
- すべてのdocstringとコメントは日本語で記述
- 可読性を最優先し、複雑なロジックには必ず日本語コメントを付与
- DRY原則を遵守し、重複コードを排除
- PEP 8準拠（ruffで自動チェック）

---

## Success Criteria

すべてのタスクが完了し、以下の条件を満たした時点で本機能は完成とする：

- **SC-001**: バックテストから実運用への転用時に、同一日時・同一データでiterationを実行した場合、生成される注文内容（銘柄、数量、価格）が100%一致する
- **SC-002**: シグナル計算ロジックを外部で検証した後、コードを変更せずにバックテストループに組み込み、1回の実行で期待通りのパフォーマンス指標が算出される
- **SC-003**: データソース追加時、設定の追加のみでシステムがそのデータを認識し、指定windowで取得できる（コード変更不要）
- **SC-004**: 実運用時の約定情報とバックテスト結果を比較した際、乖離の原因が特定できる詳細情報が提供される
- **SC-005**: パラメータ評価において、複数のパラメータの組に対して順位相関係数の分布が可視化され、オーバーフィットの有無を判断できる
- **SC-006**: データ欠損や設定エラーが発生した場合、システムは適切なエラーメッセージを出力し、復旧可能な状態を保つ
- **SC-007**: mypy strictモードで型エラーゼロ
- **SC-008**: ruff checkで違反ゼロ
- **SC-009**: すべての公開APIに日本語docstringが付与されている
- **SC-010**: quickstart.mdの手順で実際にバックテストが実行できる
