# Speckit ワークフローガイド

このドキュメントでは、`.claude/commands/` 配下のspeckitコマンドを使用した開発ワークフローを解説する。

## 概要

speckitは、仕様策定から実装・検証まで一貫したプロセスを提供するコマンド群。各コマンドは特定のフェーズを担当し、成果物を次のフェーズへ引き継ぐ。

```
specify → clarify → plan → review → validate → tasks → analyze → implement → verify
```

## フロー詳細

### 1. `/speckit.specify` - 要件定義

**目的**: 自然言語の機能説明から仕様書（spec.md）を生成する。

**実行例**:
```
/speckit.specify ユーザー認証機能を追加したい
```

**処理内容**:
1. 機能名から適切なブランチ名を生成（例: `001-user-auth`）
2. 既存ブランチとの重複をチェック
3. 新規ブランチとスペックディレクトリを作成
4. spec-templateに基づいてspec.mdを生成
5. 品質チェックリストを作成・検証

**成果物**:
- `specs/{番号}-{機能名}/spec.md`
- `specs/{番号}-{機能名}/checklists/requirements.md`

**次のステップ**: 仕様に曖昧な点がある場合は `/speckit.clarify`、問題なければ `/speckit.plan` へ進む。

---

### 2. `/speckit.clarify` - 要件の明確化

**目的**: 仕様書の曖昧な点を質問形式で明確化し、spec.mdに反映する。

**実行例**:
```
/speckit.clarify
```

**処理内容**:
1. spec.mdを読み込み、曖昧な箇所を分類・検出
2. 優先度順に最大5つの質問を**1つずつ**提示
3. 各回答をspec.mdの適切なセクションに即座反映
4. Clarificationsセクションに質疑応答を記録

**ポイント**:
- 各質問には推奨オプションが提示される
- "yes"や"recommended"で推奨を受け入れ可能
- 質問は1つずつ順次処理される

**成果物**:
- 更新された `spec.md`（Clarificationsセクション追加）

**次のステップ**: `/speckit.plan` で実装計画を策定。

---

### 3. `/speckit.plan` - 実装計画の策定

**目的**: 仕様書に基づいて技術的な実装計画（plan.md）と設計成果物を生成する。

**実行例**:
```
/speckit.plan
```

**処理内容**:
1. spec.mdとconstitution.mdを読み込み
2. Phase 0: 技術調査（research.md生成）
3. Phase 1: 設計・契約定義
   - data-model.md（エンティティ設計）
   - contracts/（API仕様）
   - quickstart.md（使用例）
4. 憲章との整合性チェック

**ブランチ設計のポイント**:
- 複数のブランチに分割する場合は、plan.mdのPhasesセクションで明示
- 各ブランチが独立してテスト可能な粒度を意識
- 依存関係がある場合は実装順序を明記

**成果物**:
- `plan.md`
- `research.md`
- `data-model.md`
- `contracts/*.md` または `contracts/*.yaml`
- `quickstart.md`

**次のステップ**: `/speckit.review` で計画をレビュー。

---

### 4. `/speckit.review` - 計画のレビュー・修正

**目的**: ユーザーからのフィードバックを評価し、修正提案を行う（読み取り専用）。

**実行例**:
```
/speckit.review データモデルにcreated_atフィールドを追加してほしい
```

**処理内容**:
1. ユーザーの指摘事項（UP: User Points）を抽出
2. 各UPについて関連ファイルを特定
3. 憲章との整合性をチェック
4. 各UPを `[APPLY]`（適用）または `[REJECT]`（却下）に分類
5. 修正提案レポートを出力

**ポイント**:
- このコマンドは**読み取り専用**であり、ファイルは変更しない
- レポート確認後、ユーザーが承認すれば手動または別途修正を実行
- 憲章のMUST原則に違反する変更は自動却下

**出力例**:
```markdown
### 1. Decisions & Changes
- **[APPLY] created_atフィールド追加**
  - Impact: data-model.md, contracts/api.yaml
  - Delta: Userエンティティにcreated_at: datetime追加

### 2. Spec Impact ⚠️
- Update Required: NO
```

**次のステップ**: 修正を適用後、`/speckit.validate` で実装準備状態を評価。

---

### 5. `/speckit.validate` - 実装可能性の評価

**目的**: 現在の設計成果物が詳細タスク生成（tasks.md）の準備が整っているか評価する。

**実行例**:
```
# 全体を評価
/speckit.validate

# 特定の範囲を評価
/speckit.validate ユーザー認証フロー
```

**処理内容**:
1. 設計成果物（spec.md, plan.md, data-model.md, contracts/）を読み込み
2. 明確性・一貫性・複雑性を評価
3. 3つのシナリオに分類:
   - ✅ **GREEN**: 実装準備完了
   - ⚠️ **YELLOW**: 軽微な修正が必要
   - 🛑 **RED**: 分解または再仕様化が必要

**特定ブランチの評価**:
`$ARGUMENTS`でスコープを指定すると、その範囲のみを評価対象とする。

**出力例**:
```markdown
## Feasibility Assessment: ユーザー認証フロー

**Status**: ✅ READY

| Category | Status | Notes |
|----------|--------|-------|
| Clarity | OK | 受け入れ基準が明確 |
| Consistency | OK | spec↔plan間の整合性OK |
| Complexity | Medium | 約15タスク |

**Next Step**: Run `/speckit.tasks`
```

**次のステップ**: ステータスに応じて修正または `/speckit.tasks` へ進む。

---

### 6. `/speckit.tasks` - 詳細実装計画の作成

**目的**: 設計成果物からタスクリスト（tasks.md）を生成する。

**実行例**:
```
# 新規作成
/speckit.tasks

# 特定のブランチ/スコープのみ
/speckit.tasks ユーザー認証フロー
```

**処理内容**:
1. plan.md, spec.md, data-model.md, contracts/を読み込み
2. ユーザーストーリー単位でタスクを構成
3. フェーズ分け:
   - Phase 1: セットアップ
   - Phase 2: 基盤タスク
   - Phase 3+: ユーザーストーリー別
   - Final: ポリッシュ

**タスクフォーマット**:
```
- [ ] T001 プロジェクト構造を作成
- [ ] T005 [P] src/middleware/auth.pyに認証ミドルウェアを実装
- [ ] T012 [P] [US1] src/models/user.pyにUserモデルを作成
```

**既存ファイルへの追記**:
- 実装済みブランチがある場合、`$ARGUMENTS`で追記対象を指定
- 既存のPhaseに追加するか、新規Phaseとして追加するかを明示

**成果物**:
- `tasks.md`

**次のステップ**: `/speckit.analyze` で成果物の整合性を最終評価。

---

### 7. `/speckit.analyze` - 成果物の総合評価

**目的**: spec.md、plan.md、tasks.mdの一貫性と品質を分析する（読み取り専用）。

**実行例**:
```
# 全体を評価
/speckit.analyze

# 特定ブランチ/範囲を評価
/speckit.analyze ユーザー認証フロー
```

**処理内容**:
1. 3つの成果物を読み込み
2. 以下の観点で分析:
   - 重複検出
   - 曖昧性検出
   - 仕様不足
   - 憲章との整合性
   - カバレッジギャップ
   - 不整合
3. 深刻度（CRITICAL/HIGH/MEDIUM/LOW）を割り当て

**特定ブランチの評価**:
`$ARGUMENTS`で評価範囲を限定可能。関連するユーザーストーリー・タスクのみを対象とする。

**出力例**:
```markdown
## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | HIGH | spec.md:L45 | "高速"に数値基準なし | 応答時間を定義 |

**Metrics**:
- Total Requirements: 12
- Total Tasks: 28
- Coverage: 100%
- Critical Issues: 0
```

**次のステップ**: 問題がなければ `/speckit.implement`、CRITICALがあれば先に修正。

---

### 8. `/speckit.implement` - 実装開始

**目的**: tasks.mdに基づいて実装を実行する。

**実行例**:
```
# 全タスクを実行
/speckit.implement

# 特定範囲のみ実装
/speckit.implement Phase 3: ユーザー認証
```

**処理内容**:
1. チェックリストの完了状態を確認
2. 設計成果物を読み込み
3. プロジェクトセットアップ（.gitignore等）を検証
4. フェーズ順にタスクを実行
5. 完了タスクは `[X]` にマーク

**特定ブランチの実装**:
- `$ARGUMENTS`で実装範囲を指定
- 指定されたPhaseまたはユーザーストーリーのタスクのみ実行

**実行ルール**:
- 依存関係を尊重（順次タスクは順番通り）
- `[P]`マーカーのタスクは並列実行可能
- TDDアプローチ: テスト→実装の順序
- 失敗時は停止して報告

**成果物**:
- 実装コード
- 更新された `tasks.md`（完了マーク付き）

**次のステップ**: `/speckit.verify` で実装と仕様の整合性を最終確認。

---

### 9. `/speckit.verify` - 最終検証

**目的**: 実装されたコードが仕様・設計と整合しているか監査する（読み取り専用）。

**実行例**:
```
/speckit.verify
```

**処理内容**:
1. 完了タスク（`[X]`マーク）を特定
2. 対応するコードファイルを読み込み
3. 以下を検証:
   - 機能: spec.mdのユーザーストーリーを満たしているか
   - データ整合性: data-model.mdとの一致
   - API準拠: contracts/との一致
   - 使用例: quickstart.mdとの整合性
   - エッジケース: spec.mdに記載されたケースの処理

**前提条件**:
- tasks.mdが存在すること
- 少なくとも1つのタスクが完了（`[X]`）していること

**出力例**:
```markdown
## Verification Report: ユーザー認証

**Status**: PASS
**Progress**: 15/15 Tasks Verified

### 1. Critical Discrepancies
✅ No critical implementation discrepancies found.

### 2. Specification & Design Gaps
- [Ambiguity]: セッションタイムアウトが未定義。30分で実装済み。

### 3. Recommendations
- spec.mdにセッションタイムアウト値を追記
```

---

## ワークフロー図

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Speckit Workflow                              │
└─────────────────────────────────────────────────────────────────────────┘

 ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
 │ specify  │───▶│ clarify  │───▶│   plan   │───▶│  review  │
 │ 要件定義 │    │ 要件明確化│    │ 実装計画 │    │ 計画レビュー│
 └──────────┘    └──────────┘    └──────────┘    └────┬─────┘
                                                       │
                      ┌────────────────────────────────┘
                      ▼
 ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
 │ validate │───▶│  tasks   │───▶│ analyze  │───▶│implement │
 │ 実装可能性│    │ タスク生成│    │ 成果物評価│    │  実装   │
 └──────────┘    └──────────┘    └──────────┘    └────┬─────┘
                                                       │
                      ┌────────────────────────────────┘
                      ▼
                 ┌──────────┐
                 │  verify  │
                 │ 最終検証 │
                 └──────────┘
```

## 補足: ブランチ戦略

複数機能を並行開発する場合:

1. **plan時点でブランチ粒度を決定**
   - 各ブランチが独立してテスト可能な単位
   - 依存関係を明確化

2. **validate/tasks/analyzeで範囲を指定**
   - 引数で対象ブランチ・ユーザーストーリーを限定
   - 既存のtasks.mdへの追記か新規かを明示

3. **implementで段階的に実装**
   - 優先度順（P1→P2→P3）に実装
   - 各ブランチ完了後にverifyで検証

## 補足: 読み取り専用コマンド

以下のコマンドはファイルを変更しない:
- `/speckit.review` - 修正提案のみ
- `/speckit.validate` - 評価レポートのみ
- `/speckit.analyze` - 分析レポートのみ
- `/speckit.verify` - 検証レポートのみ
