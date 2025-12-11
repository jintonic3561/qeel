# Implementation Branch Status

実装ブランチの進捗一覧。完了済みタスクの詳細は `tasks_archive.md` を参照。

## Phase 1: Core Infrastructure（基盤構築）

- [x] **002-core-config-and-schemas** - 設定管理とスキーマバリデーションの基盤 (T001-T045)
- [x] **004-data-source-abc** - データソースABCと共通ヘルパーメソッド (T046-T057)
- [x] **005-calculator-abc** - シグナル計算ABCとサンプル実装 (T058-T076)
- [x] **006-io-and-context-management** - IOレイヤーとコンテキスト管理 (T077-T104)
- [x] **007-exchange-client-and-mock** - 取引所クライアントABCとモック約定・ポジション管理 (T105-T144)

## Phase 2: Core Engine（P1対応）

- [x] **008-portfolio-and-orders** - ポートフォリオ構築・注文生成のABCとデフォルト実装
- [x] **009-strategy-engine** - StrategyEngine実装（ステップ単位実行）
- [ ] **010-backtest-runner** - BacktestRunner実装（ループ管理）
- [ ] **011-metrics-calculation** - パフォーマンス指標計算

## Phase 3: Production Examples（P2対応）

- [ ] **012-executor-examples** - 実運用用Executor実装例とデプロイメントドキュメント

## Phase 4 & 5: Signal Analysis / Backtest-Live Divergence（P3対応）

- [ ] **013-return-calculator-abc** - リターン計算ABCとデフォルト実装
- [ ] **014-signal-analysis** - シグナル分析機能
- [ ] **015-backtest-live-divergence** - バックテストと実運用の差異検証

---

## Branch 009: StrategyEngine実装（ステップ単位実行）

**Purpose**: バックテストと実運用で共通のStrategyEngineを実装する。各ステップ（シグナル計算、ポートフォリオ構築、注文生成、注文執行）を独立して実行可能にし、実運用では外部スケジューラから各ステップを呼び出せるようにする。

**Dependencies**: 004-data-source-abc, 005-calculator-abc, 006-io-and-context-management, 007-exchange-client-and-mock, 008-portfolio-and-orders

**FR対応**: FR-004, FR-005, FR-006, FR-011, FR-012, FR-013, FR-014

### Format: `[ID] [P?] Description`

- **[P]**: 並列実行可能（異なるファイル、依存関係なし）

---

### Phase 1: Setup（プロジェクト構造）

- [x] T145 src/qeel/core/ディレクトリと__init__.pyを作成
- [x] T146 [P] tests/unit/test_strategy_engine.pyを作成（空のテストファイル）
- [x] T147 [P] tests/integration/test_strategy_engine_integration.pyを作成（空のテストファイル）

---

### Phase 2: ステップ名定義とバリデーション

**Purpose**: StrategyEngineで使用するステップ名をEnumで定義し、型安全性を確保

- [x] T148 ステップ名EnumのRed: tests/unit/test_strategy_engine.pyにStepName Enumのテストを作成
  - ステップ名が正しく定義されていることを検証: calculate_signals, construct_portfolio, create_entry_orders, create_exit_orders, submit_entry_orders, submit_exit_orders
  - Enumの値からステップ名文字列を取得できることを検証

- [x] T149 ステップ名EnumのGreen: src/qeel/core/strategy_engine.pyにStepName Enumを実装
  - CALCULATE_SIGNALS = "calculate_signals"
  - CONSTRUCT_PORTFOLIO = "construct_portfolio"
  - CREATE_ENTRY_ORDERS = "create_entry_orders"
  - CREATE_EXIT_ORDERS = "create_exit_orders"
  - SUBMIT_ENTRY_ORDERS = "submit_entry_orders"
  - SUBMIT_EXIT_ORDERS = "submit_exit_orders"

---

### Phase 3: StrategyEngine初期化

**Purpose**: 依存コンポーネント（DataSources, Calculator, OrderCreators, ExchangeClient, ContextStore）を受け取る初期化処理

- [x] T150 StrategyEngine初期化のRed: tests/unit/test_strategy_engine.pyに初期化テストを作成
  - 必須コンポーネント（config, data_sources, signal_calculator, portfolio_constructor, entry_order_creator, exit_order_creator, exchange_client, context_store）を受け取ることを検証
  - 各コンポーネントがプロパティとしてアクセス可能であることを検証

- [x] T151 StrategyEngine初期化のGreen: src/qeel/core/strategy_engine.pyにStrategyEngineクラスの__init__を実装
  - 引数: config: Config, data_sources: dict[str, BaseDataSource], signal_calculator: BaseSignalCalculator, portfolio_constructor: BasePortfolioConstructor, entry_order_creator: BaseEntryOrderCreator, exit_order_creator: BaseExitOrderCreator, exchange_client: BaseExchangeClient, context_store: ContextStore | InMemoryStore
  - 各引数をインスタンス変数として保持
  - `_context: Context | None = None`を初期化（load_context()で設定される）

---

### Phase 4: run_step（単一ステップ実行）

**Purpose**: 指定されたステップを1回だけ実行し、コンテキストを更新する

#### 4.1 calculate_signalsステップ

- [x] T152 calculate_signalsステップのRed: テストを作成
  - run_step(date, StepName.CALCULATE_SIGNALS)を呼び出し
  - データソースからデータを取得し、signal_calculator.calculate()を呼び出すことを検証
  - 結果がContextのsignalsに設定されることを検証
  - ContextStoreに保存されることを検証

- [x] T153 calculate_signalsステップのGreen: StrategyEngine._run_calculate_signals()を実装
  - `_fetch_data_sources(date) -> dict[str, pl.DataFrame]`を呼び出してデータを取得:
    - 各BaseDataSourceに対して`_get_data_fetch_range(date, ds.config)`で(start, end)を計算
    - `ds.fetch(start, end, config.loop.universe or [])`を呼び出し
    - 結果を`dict[str, pl.DataFrame]`に格納（キーはデータソース名）
  - `signal_calculator.calculate(data_dict)`を呼び出し（引数は`dict[str, pl.DataFrame]`）
  - Contextのsignalsを更新
  - context_store.save_signals()で保存

#### 4.2 construct_portfolioステップ

- [x] T154 construct_portfolioステップのRed: テストを作成
  - run_step(date, StepName.CONSTRUCT_PORTFOLIO)を呼び出し
  - 前ステップのsignalsを使用してportfolio_constructor.construct()を呼び出すことを検証
  - 結果がContextのportfolio_planに設定されることを検証

- [x] T155 construct_portfolioステップのGreen: StrategyEngine._run_construct_portfolio()を実装
  - Contextからsignalsを取得
  - exchange_client.fetch_positions()でポジションを取得（最新状態を保証するため毎回呼び出す）
  - portfolio_constructor.construct(signals, positions)を呼び出し
  - Contextのportfolio_planを更新
  - context_store.save_portfolio_plan()で保存

#### 4.3 create_entry_ordersステップ

- [x] T156 create_entry_ordersステップのRed: テストを作成
  - run_step(date, StepName.CREATE_ENTRY_ORDERS)を呼び出し
  - portfolio_plan, positions, ohlcvを使用してentry_order_creator.create()を呼び出すことを検証
  - 結果がContextのentry_ordersに設定されることを検証

- [x] T157 create_entry_ordersステップのGreen: StrategyEngine._run_create_entry_orders()を実装
  - Contextからportfolio_planを取得
  - exchange_client.fetch_positions()でポジションを取得（最新状態を保証するため毎回呼び出す）
  - `_fetch_ohlcv_for_step(date) -> pl.DataFrame`を呼び出してOHLCVを取得:
    - ohlcvデータソースの設定から`_get_data_fetch_range(date, ohlcv_config)`で(start, end)を計算
    - `data_sources["ohlcv"].fetch(start, end, universe)`を呼び出し
    - 実運用でrun_stepを独立デプロイしても同一の期間計算ロジックが適用される
  - entry_order_creator.create(portfolio_plan, positions, ohlcv)を呼び出し
  - Contextのentry_ordersを更新
  - context_store.save_entry_orders()で保存

#### 4.4 create_exit_ordersステップ

- [x] T158 create_exit_ordersステップのRed: テストを作成
  - run_step(date, StepName.CREATE_EXIT_ORDERS)を呼び出し
  - positions, ohlcvを使用してexit_order_creator.create()を呼び出すことを検証
  - 結果がContextのexit_ordersに設定されることを検証

- [x] T159 create_exit_ordersステップのGreen: StrategyEngine._run_create_exit_orders()を実装
  - exchange_client.fetch_positions()でポジションを取得（最新状態を保証するため毎回呼び出す）
  - `_fetch_ohlcv_for_step(date)`を呼び出してOHLCVを取得（T157と同一ロジック）
  - exit_order_creator.create(positions, ohlcv)を呼び出し
  - Contextのexit_ordersを更新
  - context_store.save_exit_orders()で保存

#### 4.5 submit_entry_ordersステップ

- [x] T160 submit_entry_ordersステップのRed: テストを作成
  - run_step(date, StepName.SUBMIT_ENTRY_ORDERS)を呼び出し
  - Contextのentry_ordersをexchange_client.submit_orders()に渡すことを検証

- [x] T161 submit_entry_ordersステップのGreen: StrategyEngine._run_submit_entry_orders()を実装
  - Contextからentry_ordersを取得
  - entry_ordersが空でない場合のみexchange_client.submit_orders(entry_orders)を呼び出し

#### 4.6 submit_exit_ordersステップ

- [x] T162 submit_exit_ordersステップのRed: テストを作成
  - run_step(date, StepName.SUBMIT_EXIT_ORDERS)を呼び出し
  - Contextのexit_ordersをexchange_client.submit_orders()に渡すことを検証

- [x] T163 submit_exit_ordersステップのGreen: StrategyEngine._run_submit_exit_orders()を実装
  - Contextからexit_ordersを取得
  - exit_ordersが空でない場合のみexchange_client.submit_orders(exit_orders)を呼び出し

#### 4.7 run_stepメソッドの統合

- [x] T164 run_stepメソッドのRed: run_step統合テストを作成
  - run_step(date, step_name)が正しいプライベートメソッドにディスパッチすることを検証
  - 不正なステップ名でValueErrorが発生することを検証
  - current_datetimeがContextに設定されることを検証

- [x] T165 run_stepメソッドのGreen: StrategyEngine.run_step()を実装
  - step_nameに基づいて適切な_run_XXX()メソッドを呼び出し
  - 実行前にContextのcurrent_datetimeを設定
  - 不正なstep_nameはValueErrorをraise

---

### Phase 5: run_steps（複数ステップ実行）

**Purpose**: 複数のステップを指定順序で逐次実行する

- [x] T166 run_stepsのRed: tests/unit/test_strategy_engine.pyにrun_stepsテストを作成
  - run_steps(date, [step1, step2, step3])が各ステップを順番に実行することを検証
  - 空のリストを渡した場合は何も実行しないことを検証

- [x] T167 run_stepsのGreen: StrategyEngine.run_steps()を実装
  - step_namesリストをループし、各ステップでrun_step()を呼び出し

---

### Phase 6: run_all_steps（全ステップ実行）

**Purpose**: 1 iterationの全ステップを標準順序で実行する（バックテスト用）

- [x] T168 run_all_stepsのRed: テストを作成
  - run_all_steps(date)が全6ステップを標準順序で実行することを検証
  - 標準順序: calculate_signals → construct_portfolio → create_exit_orders → create_entry_orders → submit_exit_orders → submit_entry_orders

- [x] T169 run_all_stepsのGreen: StrategyEngine.run_all_steps()を実装
  - 標準順序でrun_steps()を呼び出し

---

### Phase 7: データ取得期間の計算

**Purpose**: 各データソースの設定（window_seconds, offset_seconds）を考慮してデータ取得期間を計算する

- [x] T170 データ取得期間計算のRed: テストを作成
  - _get_data_fetch_range(date, data_source_config)が正しい(start, end)を返すことを検証
  - window_secondsで取得範囲を決定することを検証
  - offset_secondsでリーク防止のためのオフセット調整を検証

- [x] T171 データ取得期間計算のGreen: StrategyEngine._get_data_fetch_range()を実装
  - end = date - offset_seconds
  - start = end - window_seconds
  - (start, end)タプルを返す

---

### Phase 8: コンテキスト復元機能

**Purpose**: 実運用で前回のコンテキストを復元してステップを継続実行可能にする

- [x] T172 コンテキスト復元のRed: テストを作成
  - load_context(date)で指定日付のコンテキストを復元できることを検証
  - load_context()（引数なし）で最新のコンテキストを復元できることを検証
  - コンテキストが存在しない場合は新規Contextを作成することを検証

- [x] T173 コンテキスト復元のGreen: StrategyEngine.load_context()を実装
  - `load_context(date: datetime | None = None)`シグネチャ
  - dateが指定されている場合: context_store.load(date, exchange_client)を呼び出し
  - dateがNoneの場合: context_store.load_latest(exchange_client)を呼び出し
  - 結果がNoneの場合は新規Contextを生成（current_datetime=date、その他はNone）
  - self._contextに設定して返す

---

### Phase 9: エラーハンドリング

**Purpose**: 各ステップでのエラーを適切に処理し、デバッグ情報を提供する

- [x] T174 エラーハンドリングのRed: テストを作成
  - データ取得失敗時にStrategyEngineErrorが発生することを検証
  - シグナル計算失敗時にStrategyEngineErrorが発生することを検証
  - エラーメッセージに失敗したステップ名と日付が含まれることを検証

- [x] T175 エラーハンドリングのGreen: StrategyEngineError例外クラスとエラーハンドリングを実装
  - StrategyEngineError(message, step_name, date, original_error)を定義
  - 各_run_XXX()メソッドでtry-exceptでラップし、詳細なエラー情報を含むStrategyEngineErrorをraise

---

### Phase 10: 統合テスト

**Purpose**: 全コンポーネントを結合したE2Eテスト

- [x] T176 統合テストのセットアップ: tests/integration/test_strategy_engine_integration.pyにフィクスチャを作成
  - MockDataSource、MockExchangeClient、InMemoryStore、サンプルSignalCalculator等のフィクスチャ

- [x] T177 [P] 統合テスト: calculate_signalsからsubmit_ordersまでの一連の流れをテスト
  - モックデータ（2銘柄、3日分OHLCV）を使用してrun_all_steps()を実行
  - 検証条件:
    - Context.signalsが非空で、SignalSchemaに準拠（datetime, symbol列あり）
    - Context.portfolio_planが非空で、PortfolioSchemaに準拠
    - Context.entry_ordersが生成され、OrderSchemaに準拠（symbol, side, quantity列あり）
    - Context.exit_ordersが生成され、OrderSchemaに準拠
    - MockExchangeClient.fill_historyに約定履歴が追加されている

- [x] T178 [P] 統合テスト: 複数日連続実行のテスト
  - 2日分のiterationを実行（day1, day2）
  - 検証条件:
    - day1のrun_all_steps()後、exchange_client.fetch_positions()でポジションが存在
    - day2のrun_all_steps()後、ポジション数量が累積計算されている
    - fill_historyに両日の約定が含まれている

- [x] T179 [P] 統合テスト: コンテキスト復元とステップ独立実行テスト（FR-012対応）
  - シナリオA: 部分実行→復元→継続
    - 1日目を途中まで実行（calculate_signals, construct_portfolio）
    - 新規StrategyEngineインスタンスを作成
    - load_context(day1)でコンテキストを復元
    - 残りのステップ（create_exit_orders, create_entry_orders, submit_exit_orders, submit_entry_orders）を実行
    - 全ステップが正常に完了し、約定が生成されることを検証
  - シナリオB: 単一ステップ独立実行（実運用想定）
    - load_context(day1)後、run_step(day1, StepName.CALCULATE_SIGNALS)のみ実行
    - Context.signalsが設定され、他の要素はNoneのままであることを検証

---

### Phase 11: __init__.pyエクスポートと技術的負債解消

- [x] T180 src/qeel/core/__init__.pyにStrategyEngine, StepName, StrategyEngineErrorをエクスポート
- [x] T181 src/qeel/__init__.pyにcoreモジュールをエクスポート
- [x] T186 [P] 技術的負債解消: ExchangeClientProtocolの削除
  - src/qeel/stores/context_store.py: ExchangeClientProtocolを削除し、`from qeel.exchange_clients.base import BaseExchangeClient`をimport
  - src/qeel/stores/in_memory.py: 同様にExchangeClientProtocolを削除し、BaseExchangeClientをimport
  - 型ヒントを`exchange_client: BaseExchangeClient`に変更
  - TODO(007)コメントを削除

---

### Phase 12: 品質チェック

- [x] T182 全テストがパスすることを確認: `uv run pytest tests/unit/test_strategy_engine.py tests/integration/test_strategy_engine_integration.py -v`
- [x] T183 mypyチェック: `uv run mypy src/qeel/core/ src/qeel/stores/`
- [x] T184 ruffチェック: `uv run ruff check src/qeel/core/ src/qeel/stores/ tests/unit/test_strategy_engine.py tests/integration/test_strategy_engine_integration.py`
- [x] T185 ruff format: `uv run ruff format src/qeel/core/ src/qeel/stores/ tests/unit/test_strategy_engine.py tests/integration/test_strategy_engine_integration.py`

---

## Dependencies & Execution Order

### Task Dependencies

- **Phase 1 (Setup)**: 依存なし - 即時開始可能
- **Phase 2 (ステップ名)**: Phase 1完了後
- **Phase 3 (初期化)**: Phase 2完了後
- **Phase 4 (各ステップ実装)**: Phase 3完了後 - 4.1〜4.6は順次実行
- **Phase 5 (run_steps)**: Phase 4完了後
- **Phase 6 (run_all_steps)**: Phase 5完了後
- **Phase 7 (データ取得期間)**: Phase 3と並行可能
- **Phase 8 (コンテキスト復元)**: Phase 3完了後
- **Phase 9 (エラーハンドリング)**: Phase 4〜6完了後
- **Phase 10 (統合テスト)**: Phase 9完了後
- **Phase 11 (エクスポート)**: Phase 10完了後
- **Phase 12 (品質チェック)**: Phase 11完了後

### Parallel Opportunities

- T146, T147: 並列実行可能（空のテストファイル作成）
- T177, T178, T179: 並列実行可能（独立した統合テスト）
- T180, T181, T186: 並列実行可能（__init__.pyエクスポートとProtocol削除）

---

## Implementation Notes

### StrategyEngineの設計思想

1. **ステップ単位実行**: 各ステップを独立して実行可能にすることで、実運用では外部スケジューラ（cron、Lambda等）から個別にステップを呼び出せる
2. **コンテキスト永続化**: ステップ間でコンテキストを保存・復元することで、ステップ間の時間間隔を任意に設定可能
3. **バックテストとの互換性**: BacktestRunnerはStrategyEngine.run_all_steps()を繰り返し呼び出すだけで、同一のロジックでバックテストを実行可能

### run_all_stepsの標準順序

バックテスト用の標準順序は以下の通り:
1. calculate_signals - シグナル計算
2. construct_portfolio - ポートフォリオ構築
3. create_exit_orders - エグジット注文生成（先に決済）
4. create_entry_orders - エントリー注文生成
5. submit_exit_orders - エグジット注文執行
6. submit_entry_orders - エントリー注文執行

エグジットを先に行う理由: 資金効率の観点から、既存ポジションを決済してから新規エントリーを行う。

### StepTimingConfigの使用について

`StepTimingConfig`（各ステップの実行タイミングオフセット）は、**010-backtest-runner**ブランチの責務とする。
StrategyEngineは`run_step(date, step_name)`を受け取り、dateに基づいてデータを取得する。
タイミング制御（例: シグナル計算を9:00、注文執行を15:00に行う）はBacktestRunnerまたは外部スケジューラが担当する。

### TDD品質ゲートの実行タイミング

各Red-Greenペアのタスク完了後、以下のコマンドを実行して品質を確認する:
```bash
uv run pytest tests/unit/test_strategy_engine.py -v --tb=short
uv run mypy src/qeel/core/
uv run ruff check src/qeel/core/
```
Phase 10（統合テスト）以降は統合テストも含める。最終的なPhase 12で全体の品質チェックを行う。

### データフロー

```
データソース → calculate_signals → signals
signals + positions → construct_portfolio → portfolio_plan
portfolio_plan + positions + ohlcv → create_entry_orders → entry_orders
positions + ohlcv → create_exit_orders → exit_orders
exit_orders → submit_exit_orders → exchange_client
entry_orders → submit_entry_orders → exchange_client
```

### 実運用での使用例

```python
# Lambda/cron等から呼び出し
engine = StrategyEngine(config, data_sources, ...)
engine.load_context()  # 前回のコンテキストを復元
engine.run_step(today, StepName.CALCULATE_SIGNALS)
# 数時間後
engine.load_context()
engine.run_step(today, StepName.CONSTRUCT_PORTFOLIO)
# ...以降同様
```

---

