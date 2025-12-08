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

