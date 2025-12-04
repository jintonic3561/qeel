# Implementation Plan: Qeel - 量的トレーディング向けバックテストライブラリ

**Branch**: `001-qeel-core` | **Date**: 2025-11-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/app/specs/001-qeel-core/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

バックテストから実運用へのシームレスな接続を可能とするPythonバックテストライブラリを開発する。固定幅（日足、週足、時間足）のiterationベースでループを実行し、シグナル計算・銘柄選定・執行・パフォーマンス計算を分離して実装可能にする。PolarsとPydanticを活用し、型安全性とデータバリデーションを確保する。ユーザは抽象基底クラスを継承してカスタムロジックを実装し、バックテストと実運用で同一コードを使用できる。

## Technical Context

**Language/Version**: Python 3.11+（型ヒント必須、dataclass/Pydantic活用）
**Primary Dependencies**: Polars（データフレーム操作）、Pydantic（スキーマ定義・バリデーション）、tomli（設定読み込み）
**Storage**: ローカルファイルシステム（バックテスト時）、S3/データベース（実運用時、ユーザ実装）
**Testing**: pytest、pytest-mock（TDD厳守、Red-Green-Refactor）
**Target Platform**: ローカルマシン（Linux/macOS/Windows）、パッケージとして配布可能
**Project Type**: single（Pythonライブラリパッケージ）
**Performance Goals**: 仕様から削除（ユーザマシン依存、Polarsの高速性に依存）
**Constraints**:
  - 型安全性必須（mypy strictモード）
  - NaN/null処理はユーザ責任
  - toml設定の厳密なバリデーション
  - バックテストと実運用の完全な再現性
**Scale/Scope**:
  - 複数銘柄同時トレード対応
  - 複数データソース（OHLCV、決算情報等）
  - 拡張可能な抽象基底クラス設計
  - パッケージとしてインストール可能

**Design Philosophy**:
  - **Single Engine with Step Execution**: バックテストと実運用で同一の`StrategyEngine`クラスを使用する。`StrategyEngine`はステップ単位実行メソッド（`run_step`, `run_steps`）を提供し、各ステップ間でコンテキストを永続化する。バックテストは`BacktestRunner`が`StrategyEngine.run_step`を繰り返し呼び出し、実運用は外部スケジューラ（cron、Lambda EventBridge等）が`StrategyEngine.run_step`を呼び出す
  - **Composition over Inheritance**: `BacktestRunner`は`StrategyEngine`を継承せず、インスタンスを保持（コンポジション）。ループ管理とタイミング制御のみを担当し、ステップ実行は`StrategyEngine`に委譲
  - **Rationale**: 継承階層を排除し、責任分離を明確化（StrategyEngine: ステップ実行、BacktestRunner: ループ管理）。テスタビリティ向上（StrategyEngineを単独でテスト可能）。サーバーレス環境（Lambda等）での運用を可能にし、各ステップを数時間空けて実行可能

## Constitution Check

### I. 日本語優先

✅ **準拠**: すべてのドキュメント（spec.md、plan.md、今後のコード内docstring/コメント）は日本語で記述する。

### II. 可読性最重視

✅ **準拠**:
- 変数名・関数名は明確に（`BaseSignalCalculator`、`calculate_signals`等）
- 複雑なロジック（iteration管理、データソース取得）には日本語コメント必須
- ABCパターンで拡張ポイントを明確化し、可読性を確保

### III. テスト駆動開発（TDD）

✅ **準拠**:
- pytest使用、Red-Green-Refactorサイクル厳守
- 各User Storyに対応するAcceptance Testを先行作成
- モックを活用してテスタビリティを確保（データソース、取引所API）

### IV. 型安全性の確保

✅ **準拠**:
- Python 3.11+ with 型ヒント必須
- Pydanticモデルですべての入出力スキーマを定義
- mypy strictモードで型エラーゼロを維持
- Polars DataFrameの列スキーマをPydanticで検証

### V. パッケージ構造の明確化

✅ **準拠**:
- `src/qeel/` をトップレベルパッケージとする
- `__init__.py` をすべてのディレクトリに配置
- 絶対import使用（`from qeel.core.strategy_engine import StrategyEngine`）
- `pyproject.toml` でパッケージ管理

### 判定

**✅ PASS**: すべての憲章原則に準拠しており、違反なし。Phase 0に進行可能。

## Feature Branch Strategy

このブランチ（`001-qeel-core`）では実装は行わず、適切な粒度で機能ブランチを作成し、段階的に実装を進める。各機能ブランチでは、その範囲に特化したspecを立て、TDDで実装する。

### ブランチ粒度の設計原則

1. **独立性**: 各ブランチは他のブランチに依存せず、独立してテスト・マージ可能
2. **User Story対応**: P1 → P2 → P3の順に優先度順で実装
3. **縦割り実装**: 1つのUser Storyを満たす最小限の機能を縦割りで実装（ABC定義 → 実装 → テスト）
4. **段階的統合**: 各ブランチをマージ後、次のブランチで機能を拡張

### 提案する機能ブランチ

#### Phase 1: Core Infrastructure（基盤構築）

**Branch**: `002-core-config-and-schemas`
- **目的**: 設定管理とスキーマバリデーションの基盤
- **成果物**:
  - `qeel/config/` - Pydantic設定モデル（Config, DataSourceConfig, CostConfig, LoopConfig, TimingConfig, ContextStoreConfig）
  - `qeel/schemas/` - DataFrameスキーマバリデータ（OHLCVSchema, SignalSchema等）
  - toml読み込み・バリデーション機能（research.mdの設定例を参照）
  - 型ヒント + mypy設定
- **テスト**: 不正なtomlでValidationError、正常なtomlで正しくロード
- **依存**: なし
- **User Story**: N/A（基盤）
- **責任範囲**: toml設定ファイルのスキーマ定義とバリデーションロジック。データソースの実装は004で行う

---

**Branch**: `003-utils-infrastructure`
- **目的**: 実運用Executor実装を支援するユーティリティ群（FR-031）
- **成果物**:
  - `qeel/utils/retry.py` - APIリトライロジック（exponential backoff、タイムアウト）
  - `qeel/utils/notification.py` - エラー通知ヘルパー（Slack等）
  - `qeel/utils/rounding.py` - 数量・価格の丸め処理（`round_to_unit(value, unit)`）
  - 型ヒント完備、可読性重視の実装
- **テスト**: モックAPIクライアントでリトライ動作確認、通知送信のモック確認、丸め処理の精度検証
- **依存**: `002-core-config-and-schemas`
- **User Story**: User Story 2（実運用支援、オプション機能）
- **備考**: ユーザはこれらのutilsを自由に利用可能だが、利用は強制ではない。Executor実装時の負担を軽減する目的

---

**Branch**: `004-data-source-abc`
- **目的**: データソースABCと共通ヘルパーメソッド、テスト用実装
- **成果物**:
  - `qeel/data_sources/base.py` - BaseDataSource ABC
    - `_normalize_datetime_column()`: datetime列の正規化
    - `_adjust_window_for_offset()`: offset_secondsによるwindow調整（リーク防止）
    - `_filter_by_datetime_and_symbols()`: datetime範囲と銘柄でフィルタリング
  - `qeel/data_sources/mock.py` - MockDataSource（テスト用）
- **テスト**: モックデータでfetch()が正しく動作、ヘルパーメソッドの動作確認
- **依存**: `002-core-config-and-schemas`
- **User Story**: N/A（基盤、User Story 1で使用）
- **責任範囲**: DataSourceConfigを受け取り、実際のデータ取得を実装。設定スキーマは002で定義済み。共通前処理をヘルパーメソッドとして提供し、ユーザは任意に利用可能
- **備考**: 任意のスキーマを許容し、強制的なバリデーションを行わない。ユーザは独自のデータソース（Parquet、API、データベース等）を自由に実装可能

---

**Branch**: `005-calculator-abc`
- **目的**: シグナル計算ABCとサンプル実装
- **成果物**:
  - `qeel/calculators/signals/base.py` - BaseSignalCalculator ABC
  - `qeel/examples/signals/moving_average.py` - 移動平均クロス実装例
  - Pydanticパラメータモデル
- **テスト**: モックデータでcalculate()が正しく動作
- **依存**: `002-core-config-and-schemas`
- **User Story**: User Story 1（シグナル計算）

---

#### Phase 2: Core Engine（P1対応）

**Branch**: `006-io-and-context-management`
- **目的**: IOレイヤーとコンテキスト管理
- **成果物**:
  - `qeel/models/context.py` - Context Pydanticモデル
  - `qeel/io/base.py` - BaseIO ABC
  - `qeel/io/local.py` - LocalIO実装
  - `qeel/io/s3.py` - S3IO実装
  - `qeel/stores/context_store.py` - ContextStore（単一実装、IOレイヤー依存）
  - `qeel/stores/in_memory.py` - InMemoryStore（テスト用）
- **テスト**: IOレイヤーのsave/load/exists動作確認、ContextStoreがIOレイヤー経由で各要素を個別に保存、load()が指定日付のコンテキストを復元、load_latest()が最新日付のコンテキストを復元、存在しない要素はNone、S3IOはモックboto3で動作確認
- **依存**: `002-core-config-and-schemas`
- **User Story**: User Story 1（コンテキスト永続化、トレーサビリティ確保）、User Story 2（実運用でS3使用）
- **備考**: IOレイヤーで Local/S3 の判別を一手に引き受け、DRY原則を遵守。ContextStoreはIOレイヤーに依存し、Local/S3の判別ロジックを持たない

---

**Branch**: `007-exchange-client-and-mock`
- **目的**: 取引所クライアントABCとモック約定・ポジション管理
- **成果物**:
  - `qeel/exchange_clients/base.py` - BaseExchangeClient ABC
  - `qeel/exchange_clients/mock.py` - MockExchangeClient（バックテスト用）
  - コスト計算ロジック（手数料、スリッページ）
- **テスト**: モック約定が正しく生成される、コスト反映
- **依存**: `002-core-config-and-schemas`
- **User Story**: User Story 1（約定シミュレーション）

---

**Branch**: `008-portfolio-and-orders`
- **目的**: ポートフォリオ構築・注文生成のABCとデフォルト実装
- **成果物**:
  - `qeel/portfolio_constructors/base.py` - BasePortfolioConstructor ABC（戻り値を`pl.DataFrame`、メタデータ付与可能）
  - `qeel/portfolio_constructors/top_n.py` - TopNPortfolioConstructor（デフォルト実装、signal_strengthをメタデータとして返す）
  - `qeel/order_creators/base.py` - BaseOrderCreator ABC（引数`portfolio_plan`, `current_positions`, `ohlcv`）
  - `qeel/order_creators/equal_weight.py` - EqualWeightOrderCreator（デフォルト実装、メタデータ活用）
- **テスト**: モックデータでポートフォリオ構築と注文生成が正しく動作
- **依存**: `002-core-config-and-schemas`
- **User Story**: User Story 1（ポートフォリオ構築、注文生成）
- **デフォルト実装詳細**:
  - `TopNPortfolioConstructor`: シグナル上位N銘柄でポートフォリオを構築（Nはパラメータで指定、デフォルト10）。出力DataFrameには`datetime`, `symbol`, `signal_strength`（メタデータ）を含む
  - `EqualWeightOrderCreator`: 構築済みポートフォリオに等ウェイト割り当て（1/N）、open価格での成行買い、close価格での成行売り（リバランス時）。`portfolio_plan`のメタデータ（`signal_strength`等）を参照して注文生成
  - 注文タイミング: toml設定の`timing.submit_orders`で指定

---

**Branch**: `009-strategy-engine`
- **目的**: StrategyEngine実装（ステップ単位実行）
- **成果物**:
  - `qeel/core/strategy_engine.py` - StrategyEngine（単一実装、ステップ単位実行）
    - `run_step(date, step_name)`: 指定ステップのみ実行
    - `run_steps(date, step_names)`: 複数ステップを逐次実行
- **テスト**: ステップ単位実行のテスト、コンテキスト永続化の動作確認
- **依存**: `004`, `005`, `006`, `007`, `008`
- **User Story**: User Story 1（ステップ実行）、User Story 2（実運用でステップ単位実行）
- **実運用対応**: `StrategyEngine.run_step`を外部スケジューラから直接呼び出すことで、サーバーレス環境での運用が可能

---

**Branch**: `010-backtest-runner`
- **目的**: BacktestRunner実装（ループ管理、取引日判定、ユニバース管理）
- **成果物**:
  - `qeel/core/backtest_runner.py` - BacktestRunner（StrategyEngineを保持、ループ管理）
  - 取引日判定（toml設定のtradingCalendarを使用）
  - ユニバース管理ロジック
- **テスト**: E2Eでバックテスト実行、User Story 1のAcceptance Scenarios
- **依存**: `009-strategy-engine`
- **User Story**: **User Story 1（P1）完成、User Story 2（P2）のコア実装完成**
- **ユニバース管理**: `LoopConfig.universe`が指定されている場合はそのリストを`BaseDataSource.fetch()`の`symbols`引数として渡す。Noneの場合は全銘柄が対象となる。フィルタリングの結果、当日データが存在する銘柄のみが残る（自然に積集合になる）

---

**Branch**: `011-metrics-calculation`
- **目的**: パフォーマンス指標計算
- **成果物**:
  - `qeel/metrics/calculator.py` - メトリクス計算ロジック
  - シャープレシオ、最大ドローダウン、勝率等
- **テスト**: 約定データから正しく指標が算出される
- **依存**: `010-backtest-runner`
- **User Story**: User Story 1（結果検証）の完成

---

#### Phase 3: Production Examples（P2対応）

**Branch**: `012-executor-examples`
- **目的**: 実運用用Executor実装例とデプロイメントドキュメント
- **成果物**:
  - `qeel/exchange_clients/examples/exchange_api.py` - 取引所API実装例（スケルトン）
  - `docs/deployment/lambda.md` - Lambdaデプロイメント例
  - `docs/deployment/ecs.md` - ECS/Fargateデプロイメント例
  - `docs/deployment/local_cron.md` - ローカルcronデプロイメント例
  - quickstart.mdに実運用例を追加
- **テスト**: モックAPIクライアントで動作確認、Lambdaローカルテスト例
- **依存**: `010-backtest-runner`, `003-utils-infrastructure`
- **User Story**: User Story 2（API連携、デプロイメント）完全完成

---

#### Phase 4: Signal Analysis（P3対応）

**Branch**: `013-return-calculator-abc`
- **目的**: リターン計算ABCとデフォルト実装
- **成果物**:
  - `qeel/calculators/returns/base.py` - BaseReturnCalculator ABC
  - `qeel/calculators/returns/log_return.py` - 対数リターン（デフォルト実装）
- **テスト**: モックデータでリターン計算が正しく動作
- **依存**: `002-core-config-and-schemas`
- **User Story**: User Story 3（リターン計算）

---

**Branch**: `014-signal-analysis`
- **目的**: シグナル分析機能（P3完成）
- **成果物**:
  - `qeel/analysis/rank_correlation.py` - 順位相関係数計算
  - `qeel/analysis/visualizer.py` - 分布可視化
  - パラメータグリッド評価機能
- **テスト**: シグナルとリターンから順位相関が計算される
- **依存**: `005-calculator-abc`, `013-return-calculator-abc`
- **User Story**: **User Story 3（P3）完成**

---

#### Phase 5: Backtest-Live Divergence（P3対応）

**Branch**: `015-backtest-live-divergence`
- **目的**: バックテストと実運用の差異検証（P3完成）
- **成果物**:
  - `qeel/diagnostics/comparison.py` - バックテストと実運用の差異計算ロジック
  - `qeel/diagnostics/visualizer.py` - 差異可視化
  - 詳細ログ出力
- **テスト**: バックテストと実運用の約定データから差異が可視化される
- **依存**: `011-metrics-calculation`, `010-backtest-runner`
- **User Story**: **User Story 4（P3）完成**

---

### ブランチ実装順序

```
Phase 1: 基盤構築
  002 → 003 (utils)
    ↓
  002 → 004 → 005 → 並行
         ↓     ↓
  006 ← ─┘     └─→ 007

Phase 2: P1完成、P2コア実装
  008 (depends: 002) - Portfolio & Orders
   ↓
  009 (depends: 004, 005, 006, 007, 008) - StrategyEngine
   ↓
  010 (depends: 009) - BacktestRunner
   ↓
  011 - Metrics

Phase 3: P2完成（実運用例とドキュメント）
  012 (depends: 010, 003 - utils使用) - Executor Examples + Deployment Docs

Phase 4 & 5: P3完成
  013 → 014 (depends: 005, 013)
  015 (depends: 011, 010)
```

### 各ブランチでの作業手順

1. ブランチ作成: `git checkout -b <branch-name>`
2. そのブランチ専用の仕様書作成: `/speckit.specify`（必要に応じて）
3. 実装計画: `/speckit.plan`（このplan.mdを参照）
4. タスク生成: `/speckit.tasks`
5. TDDで実装: `/speckit.implement`
6. テスト完了後、PRを作成しマージ

### マイルストーン

- **M1（基盤完成）**: Branch 002-007完了 → 基盤クラスがすべて揃う
- **M2（P1完成、P2コア実装）**: Branch 008-011完了 → バックテスト機能が動作、実運用でステップ単位実行が可能
- **M3（P2完成）**: Branch 012完了 → 実運用例とデプロイメントドキュメントが揃う
- **M4（P3完成）**: Branch 013-015完了 → 分析機能が完成

## Project Structure

### Documentation (this feature)

```text
specs/001-qeel-core/
├── spec.md              # Feature specification
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output - design research and decisions
├── data-model.md        # Phase 1 output - Pydantic models and Polars schemas
├── quickstart.md        # Phase 1 output - user quickstart guide
└── contracts/           # Phase 1 output - ABC interface specifications
    ├── base_signal_calculator.md
    ├── base_return_calculator.md
    ├── base_portfolio_constructor.md
    ├── base_order_creator.md
    ├── base_data_source.md
    ├── base_exchange_client.md
    ├── base_io.md
    └── context_store.md
```

### Source Code (repository root)

Pythonライブラリパッケージとして、`src/qeel/` をトップレベルパッケージとする。

```text
src/qeel/
├── __init__.py
├── config/
│   ├── __init__.py
│   └── models.py          # Pydantic設定モデル（Config, DataSourceConfig等）
├── utils/
│   ├── __init__.py
│   ├── retry.py           # APIリトライヘルパー（exponential backoff、タイムアウト）
│   ├── notification.py    # エラー通知ヘルパー（Slack等）
│   └── rounding.py        # 数量・価格の丸め処理（round_to_unit）
├── schemas/
│   ├── __init__.py
│   └── validators.py      # Polars DataFrameスキーマバリデータ
├── data_sources/
│   ├── __init__.py
│   ├── base.py            # BaseDataSource ABC
│   ├── parquet.py         # ParquetDataSource（標準実装）
│   └── mock.py            # MockDataSource（テスト用）
├── calculators/
│   ├── __init__.py
│   ├── signals/
│   │   ├── __init__.py
│   │   └── base.py        # BaseSignalCalculator ABC
│   └── returns/
│       ├── __init__.py
│       ├── base.py        # BaseReturnCalculator ABC
│       └── log_return.py  # 対数リターン（デフォルト実装）
├── portfolio_constructors/
│   ├── __init__.py
│   ├── base.py            # BasePortfolioConstructor ABC
│   └── top_n.py           # TopNPortfolioConstructor（デフォルト実装）
├── order_creators/
│   ├── __init__.py
│   ├── base.py            # BaseOrderCreator ABC
│   └── equal_weight.py    # EqualWeightOrderCreator（デフォルト実装）
├── exchange_clients/
│   ├── __init__.py
│   ├── base.py            # BaseExchangeClient ABC
│   └── mock.py            # MockExchangeClient（バックテスト用）
├── io/
│   ├── __init__.py
│   ├── base.py            # BaseIO ABC
│   ├── local.py           # LocalIO（ローカルファイルシステム）
│   └── s3.py              # S3IO（S3ストレージ）
├── stores/
│   ├── __init__.py
│   ├── context_store.py   # ContextStore（単一実装、IOレイヤー依存）
│   └── in_memory.py       # InMemoryStore（テスト用）
├── models/
│   ├── __init__.py
│   └── context.py         # Context Pydanticモデル
├── core/
│   ├── __init__.py
│   ├── strategy_engine.py # StrategyEngine（単一実装、ステップ単位実行）
│   └── backtest_runner.py # BacktestRunner（ループ管理）
├── metrics/
│   ├── __init__.py
│   └── calculator.py      # パフォーマンス指標計算
├── analysis/
│   ├── __init__.py
│   ├── rank_correlation.py    # 順位相関係数計算
│   └── visualizer.py          # 分布可視化
├── diagnostics/
│   ├── __init__.py
│   ├── comparison.py      # バックテストと実運用の差異計算
│   └── visualizer.py      # 差異可視化
└── examples/              # 実装例を集約
    ├── __init__.py
    ├── signals/
    │   ├── __init__.py
    │   └── moving_average.py  # 移動平均クロス実装例
    └── exchange_clients/
        ├── __init__.py
        └── exchange_api.py    # 取引所API実装例（スケルトン）

tests/
├── conftest.py            # pytest共通設定、フィクスチャ
├── unit/
│   ├── test_config.py
│   ├── test_schemas.py
│   ├── test_data_sources.py
│   ├── test_calculators.py
│   ├── test_selectors.py
│   ├── test_order_creators.py
│   ├── test_executors.py
│   ├── test_stores.py
│   ├── test_core.py       # StrategyEngine, BacktestRunnerのテスト
│   ├── test_metrics.py
│   ├── test_analysis.py
│   └── test_diagnostics.py
├── integration/
│   ├── test_backtest_e2e.py
│   ├── test_live_e2e.py
│   ├── test_signal_analysis_e2e.py
│   └── test_backtest_live_divergence_e2e.py
└── contract/              # ABC契約テスト
    ├── test_signal_calculator_contract.py
    ├── test_return_calculator_contract.py
    ├── test_symbol_selector_contract.py
    ├── test_order_creator_contract.py
    ├── test_data_source_contract.py
    ├── test_executor_contract.py
    └── test_context_store_contract.py

pyproject.toml             # パッケージ設定、依存関係、mypy設定
mypy.ini                   # mypy strictモード設定
README.md                  # ユーザ向けドキュメント
```

**Structure Decision**: 単一のPythonライブラリパッケージ（Option 1: Single project）を選択。`src/qeel/` をトップレベルパッケージとし、名前空間を明確にする。すべてのディレクトリに `__init__.py` を配置し、絶対importを使用する（`from qeel.config.models import Config`）。

## Complexity Tracking

**違反なし**: Constitution Checkをすべてパスしており、複雑性の導入は不要。
