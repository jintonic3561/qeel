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

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

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
- 絶対import使用（`from qeel.core.engine import BacktestEngine`）
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
  - `qeel/config/` - Pydantic設定モデル（Config, DataSourceConfig, CostConfig, LoopConfig）
  - `qeel/schemas/` - DataFrameスキーマバリデータ（MarketDataSchema, SignalSchema等）
  - toml読み込み・バリデーション機能
  - 型ヒント + mypy設定
- **テスト**: 不正なtomlでValidationError、正常なtomlで正しくロード
- **依存**: なし
- **User Story**: N/A（基盤）

---

**Branch**: `003-data-source-abc`
- **目的**: データソースABCと標準実装
- **成果物**:
  - `qeel/data_sources/base.py` - BaseDataSource ABC
  - `qeel/data_sources/csv.py` - CSVDataSource
  - `qeel/data_sources/parquet.py` - ParquetDataSource
  - `qeel/data_sources/mock.py` - MockDataSource（テスト用）
- **テスト**: モックデータでfetch()が正しく動作、スキーマバリデーション
- **依存**: `002-core-config-and-schemas`
- **User Story**: N/A（基盤、User Story 1で使用）

---

**Branch**: `004-calculator-abc`
- **目的**: シグナル計算ABCとサンプル実装
- **成果物**:
  - `qeel/calculators/base_signal.py` - BaseSignalCalculator ABC
  - `qeel/calculators/examples/moving_average.py` - 移動平均クロス実装例
  - Pydanticパラメータモデル
- **テスト**: モックデータでcalculate()が正しく動作
- **依存**: `002-core-config-and-schemas`
- **User Story**: User Story 1（シグナル計算）

---

#### Phase 2: Backtest Engine（P1対応）

**Branch**: `005-context-management`
- **目的**: コンテキスト管理とストア
- **成果物**:
  - `qeel/models/context.py` - Context Pydanticモデル
  - `qeel/stores/base.py` - BaseContextStore ABC
  - `qeel/stores/local_json.py` - LocalJSONStore
  - `qeel/stores/in_memory.py` - InMemoryStore（テスト用）
- **テスト**: save/loadが正しく動作、存在しない場合はNone
- **依存**: `002-core-config-and-schemas`
- **User Story**: User Story 1（コンテキスト永続化）

---

**Branch**: `006-executor-and-mock`
- **目的**: 執行ABCとモック約定シミュレーション
- **成果物**:
  - `qeel/executors/base.py` - BaseExecutor ABC
  - `qeel/executors/mock.py` - MockExecutor（バックテスト用）
  - コスト計算ロジック（手数料、スリッページ）
- **テスト**: モック約定が正しく生成される、コスト反映
- **依存**: `002-core-config-and-schemas`
- **User Story**: User Story 1（約定シミュレーション）

---

**Branch**: `007-backtest-engine`
- **目的**: バックテストエンジン本体（P1完成）
- **成果物**:
  - `qeel/engines/base.py` - BaseEngine（共通フロー）
  - `qeel/engines/backtest.py` - BacktestEngine
  - iteration管理、取引日判定
  - デフォルトの銘柄選定・注文生成ロジック
- **テスト**: E2Eでバックテスト実行、User Story 1のAcceptance Scenarios
- **依存**: `003`, `004`, `005`, `006`
- **User Story**: **User Story 1（P1）完成**

---

**Branch**: `008-metrics-calculation`
- **目的**: パフォーマンス指標計算
- **成果物**:
  - `qeel/metrics/calculator.py` - メトリクス計算ロジック
  - シャープレシオ、最大ドローダウン、勝率等
- **テスト**: 約定データから正しく指標が算出される
- **依存**: `007-backtest-engine`
- **User Story**: User Story 1（結果検証）の完成

---

#### Phase 3: Production Deployment（P2対応）

**Branch**: `009-live-engine`
- **目的**: 実運用エンジン（P2完成）
- **成果物**:
  - `qeel/engines/live.py` - LiveEngine
  - バックテストとの再現性保証ロジック
  - 当日iteration実行
- **テスト**: 同一日時・データで BacktestEngine と LiveEngine が同じOrdersを生成
- **依存**: `007-backtest-engine`
- **User Story**: **User Story 2（P2）完成**

---

**Branch**: `010-executor-examples`
- **目的**: 実運用用Executor実装例
- **成果物**:
  - `qeel/executors/examples/exchange_api.py` - 取引所API実装例（スケルトン）
  - ユーザ向けドキュメント
- **テスト**: モックAPIクライアントで動作確認
- **依存**: `009-live-engine`
- **User Story**: User Story 2（API連携）

---

#### Phase 4: Signal Evaluation（P3対応）

**Branch**: `011-return-calculator-abc`
- **目的**: リターン計算ABCとサンプル実装
- **成果物**:
  - `qeel/calculators/base_return.py` - BaseReturnCalculator ABC
  - `qeel/calculators/examples/log_return.py` - 対数リターン実装例
- **テスト**: モックデータでリターン計算が正しく動作
- **依存**: `002-core-config-and-schemas`
- **User Story**: User Story 3（リターン計算）

---

**Branch**: `012-signal-evaluation`
- **目的**: シグナル評価機能（P3完成）
- **成果物**:
  - `qeel/evaluation/rank_correlation.py` - 順位相関係数計算
  - `qeel/evaluation/visualizer.py` - 分布可視化
  - パラメータグリッド評価機能
- **テスト**: シグナルとリターンから順位相関が計算される
- **依存**: `004-calculator-abc`, `011-return-calculator-abc`
- **User Story**: **User Story 3（P3）完成**

---

#### Phase 5: Divergence Analysis（P3対応）

**Branch**: `013-divergence-analysis`
- **目的**: バックテストと実運用の乖離検証（P3完成）
- **成果物**:
  - `qeel/analysis/divergence.py` - 乖離計算ロジック
  - `qeel/analysis/visualizer.py` - 乖離可視化
  - 詳細ログ出力
- **テスト**: バックテストと実運用の約定データから乖離が可視化される
- **依存**: `008-metrics-calculation`, `009-live-engine`
- **User Story**: **User Story 4（P3）完成**

---

### ブランチ実装順序

```
Phase 1: 基盤構築
  002 → 003 → 004 → 並行
         ↓     ↓
  005 ← ─┘     └─→ 006

Phase 2: P1完成
  007 (depends: 003, 004, 005, 006)
   ↓
  008

Phase 3: P2完成
  009 (depends: 007)
   ↓
  010

Phase 4 & 5: P3完成
  011 → 012 (depends: 004, 011)
  013 (depends: 008, 009)
```

### 各ブランチでの作業手順

1. ブランチ作成: `git checkout -b <branch-name>`
2. そのブランチ専用の仕様書作成: `/speckit.specify`（必要に応じて）
3. 実装計画: `/speckit.plan`（このplan.mdを参照）
4. タスク生成: `/speckit.tasks`
5. TDDで実装: `/speckit.implement`
6. テスト完了後、PRを作成しマージ

### マイルストーン

- **M1（基盤完成）**: Branch 002-006完了 → 基盤クラスがすべて揃う
- **M2（P1完成）**: Branch 007-008完了 → バックテスト機能が動作
- **M3（P2完成）**: Branch 009-010完了 → 実運用機能が動作
- **M4（P3完成）**: Branch 011-013完了 → 分析機能が完成

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
    ├── base_data_source.md
    ├── base_executor.md
    └── base_context_store.md
```

### Source Code (repository root)

Pythonライブラリパッケージとして、`src/qeel/` をトップレベルパッケージとする。

```text
src/qeel/
├── __init__.py
├── config/
│   ├── __init__.py
│   └── models.py          # Pydantic設定モデル（Config, DataSourceConfig等）
├── schemas/
│   ├── __init__.py
│   └── validators.py      # Polars DataFrameスキーマバリデータ
├── data_sources/
│   ├── __init__.py
│   ├── base.py            # BaseDataSource ABC
│   ├── csv.py             # CSVDataSource
│   ├── parquet.py         # ParquetDataSource
│   └── mock.py            # MockDataSource（テスト用）
├── calculators/
│   ├── __init__.py
│   ├── base_signal.py     # BaseSignalCalculator ABC
│   ├── base_return.py     # BaseReturnCalculator ABC
│   └── examples/
│       ├── __init__.py
│       ├── moving_average.py  # 移動平均クロス実装例
│       └── log_return.py      # 対数リターン実装例
├── executors/
│   ├── __init__.py
│   ├── base.py            # BaseExecutor ABC
│   ├── mock.py            # MockExecutor（バックテスト用）
│   └── examples/
│       ├── __init__.py
│       └── exchange_api.py    # 取引所API実装例（スケルトン）
├── stores/
│   ├── __init__.py
│   ├── base.py            # BaseContextStore ABC
│   ├── local_json.py      # LocalJSONStore
│   ├── local_parquet.py   # LocalParquetStore
│   └── in_memory.py       # InMemoryStore（テスト用）
├── models/
│   ├── __init__.py
│   └── context.py         # Context Pydanticモデル
├── engines/
│   ├── __init__.py
│   ├── base.py            # BaseEngine（共通フロー）
│   ├── backtest.py        # BacktestEngine
│   └── live.py            # LiveEngine
├── metrics/
│   ├── __init__.py
│   └── calculator.py      # パフォーマンス指標計算
├── evaluation/
│   ├── __init__.py
│   ├── rank_correlation.py    # 順位相関係数計算
│   └── visualizer.py          # 分布可視化
└── analysis/
    ├── __init__.py
    ├── divergence.py      # 乖離計算
    └── visualizer.py      # 乖離可視化

tests/
├── conftest.py            # pytest共通設定、フィクスチャ
├── unit/
│   ├── test_config.py
│   ├── test_schemas.py
│   ├── test_data_sources.py
│   ├── test_calculators.py
│   ├── test_executors.py
│   ├── test_stores.py
│   ├── test_engines.py
│   ├── test_metrics.py
│   └── test_evaluation.py
├── integration/
│   ├── test_backtest_e2e.py
│   ├── test_live_e2e.py
│   └── test_signal_evaluation_e2e.py
└── contract/              # ABC契約テスト
    ├── test_signal_calculator_contract.py
    ├── test_return_calculator_contract.py
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
