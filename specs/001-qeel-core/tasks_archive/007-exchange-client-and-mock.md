# Tasks: 007-prerequisites（007ブランチ前提条件修正）

**Input**: Design documents from `/specs/001-qeel-core/`
**Prerequisites**: 006ブランチ完了、設計ドキュメント更新済み

**Branch**: `007-exchange-client-and-mock`（前提条件修正フェーズ）
**目的**: 設計ドキュメント更新に伴う既存実装の整合性修正

**成果物**:
- `CostConfig.market_fill_price_type`フィールド追加
- `LocalIO.load()`のglobパターン対応
- `S3IO.load()`のPolarsネイティブS3読み込み対応
- `ParquetDataSource`標準実装の新規作成

**Tests**: TDDを厳守。Red-Green-Refactorサイクル必須（constitution準拠）

---

## Phase 1: CostConfig拡張（market_fill_price_type追加）

**Purpose**: MockExchangeClientの成行注文約定ロジックで使用するフィールドを追加

### Tests (TDD: RED)

- [x] T105 tests/unit/test_config.pyに以下のテストを追加:
  - `test_cost_config_market_fill_price_type_default`: デフォルト値が"next_open"であることを確認
  - `test_cost_config_market_fill_price_type_current_close`: "current_close"でバリデーションパス
  - `test_cost_config_market_fill_price_type_invalid`: 不正な値でValidationError

### Implementation (TDD: GREEN)

- [x] T106 src/qeel/config/models.pyのCostConfigに`market_fill_price_type`フィールドを追加
  - デフォルト値: "next_open"
  - バリデータ: {"next_open", "current_close"}のいずれかを許可
  - data-model.md 1.2に準拠

**Checkpoint**: `uv run pytest tests/unit/test_config.py -k market_fill_price_type` 全件パス

---

## Phase 2: BaseIO.load()のglobパターン対応

**Purpose**: ParquetDataSourceがglobパターン（`*.parquet`等）を使用できるようにする

### Tests (TDD: RED)

- [x] T107 tests/unit/test_io.pyに以下のテストを追加:
  - `test_local_io_is_glob_pattern_asterisk`: "*"を含むパスでTrueを返す
  - `test_local_io_is_glob_pattern_question`: "?"を含むパスでTrueを返す
  - `test_local_io_is_glob_pattern_bracket`: "["を含むパスでTrueを返す
  - `test_local_io_is_glob_pattern_normal`: globパターンを含まないパスでFalseを返す
  - `test_local_io_load_parquet_glob_pattern`: globパターンでPolarsに直接委譲される（存在チェックスキップ）

### Implementation (TDD: GREEN)

- [x] T108 src/qeel/io/local.pyに`_is_glob_pattern()`メソッドを追加
  - "*", "?", "["のいずれかを含む場合Trueを返す
- [x] T109 src/qeel/io/local.pyの`load()`メソッドを修正
  - parquet形式かつglobパターンの場合、存在チェックをスキップ
  - Polarsの`read_parquet()`に直接委譲（contracts/base_io.md準拠）

**Checkpoint**: `uv run pytest tests/unit/test_io.py -k glob` 全件パス

---

## Phase 3: S3IO.load()のPolarsネイティブS3対応

**Purpose**: S3上のParquetファイルをPolarsのネイティブS3サポートで読み込む

### Tests (TDD: RED)

- [x] T110 tests/unit/test_io.pyに以下のテストを追加（モックboto3使用）:
  - `test_s3_io_storage_options_initialized`: `_storage_options`が正しく初期化される
  - `test_s3_io_to_s3_uri`: `_to_s3_uri()`が正しいURI形式を返す
  - `test_s3_io_load_parquet_uses_native_s3`: parquet形式でPolarsネイティブS3読み込みを使用（モック確認）

### Implementation (TDD: GREEN)

- [x] T111 src/qeel/io/s3.pyの`__init__()`に`_storage_options`を追加
  - `{"aws_region": region}`形式
- [x] T112 src/qeel/io/s3.pyに`_to_s3_uri()`メソッドを追加
  - `f"s3://{self.bucket}/{path}"`形式でURIを返す
- [x] T113 src/qeel/io/s3.pyの`load()`メソッドを修正
  - parquet形式の場合、`pl.read_parquet(s3_uri, storage_options=self._storage_options)`を使用
  - contracts/base_io.md準拠

**Checkpoint**: `uv run pytest tests/unit/test_io.py -k s3` 全件パス（モック環境）

---

## Phase 4: ParquetDataSource標準実装

**Purpose**: quickstart.mdで参照されているParquetDataSource標準実装を提供

### Tests (TDD: RED)

- [x] T114 tests/unit/test_data_sources.pyにTestParquetDataSourceクラスを追加:
  - `test_parquet_data_source_fetch_returns_dataframe`: fetch()がDataFrameを返す
  - `test_parquet_data_source_uses_io_layer`: IOレイヤー経由でデータを読み込む
  - `test_parquet_data_source_applies_helpers`: ヘルパーメソッド（_normalize_datetime_column等）を適用
  - `test_parquet_data_source_raises_on_missing`: データが存在しない場合ValueErrorをraise

### Implementation (TDD: GREEN)

- [x] T115 src/qeel/data_sources/parquet.pyを新規作成
  - `ParquetDataSource`クラスを実装
  - contracts/base_data_source.mdの実装例に準拠
  - IOレイヤー経由でParquetファイルを読み込み
  - 共通ヘルパーメソッドを使用した前処理

- [x] T116 src/qeel/data_sources/__init__.pyに`ParquetDataSource`をエクスポート

### Integration Test

- [x] T117 tests/integration/test_data_source_integration.pyにParquetDataSource統合テストを追加:
  - `test_parquet_data_source_with_local_io`: LocalIOと連携してParquetを読み込み
  - `test_parquet_data_source_with_glob_pattern`: globパターンでの読み込み確認

**Checkpoint**: `uv run pytest tests/ -k parquet` 全件パス

---

## Phase 5: 品質ゲート確認

- [x] T118 `uv run mypy src/qeel/` 型エラーゼロ
- [x] T119 `uv run ruff check src/qeel/` リンターエラーゼロ
- [x] T120 `uv run pytest tests/` 全テストパス

**Final Checkpoint**: 007ブランチ前提条件修正完了、007本体実装に進行可能

---

# Tasks: 007-exchange-client-and-mock（本体実装）

**Input**: Design documents from `/specs/001-qeel-core/`
**Prerequisites**: 007-prerequisites（T105-T120）完了済み、contracts/base_exchange_client.md（必須）

**Branch**: `007-exchange-client-and-mock`（本体実装フェーズ）
**目的**: 取引所クライアントABCとモック約定・ポジション管理

**成果物**:
- `qeel/exchange_clients/base.py` - BaseExchangeClient ABC
- `qeel/exchange_clients/mock.py` - MockExchangeClient（バックテスト用）
- コスト計算ロジック（手数料、スリッページ）

**Tests**: TDDを厳守。Red-Green-Refactorサイクル必須（constitution準拠）

**依存ブランチ**: `006-io-and-context-management`（完了済み）、007-prerequisites（完了済み）

**Note**:
- contracts/base_exchange_client.mdの仕様に準拠して実装
- data-model.md 2.5（Order）、2.6（FillReport）、2.4（Position）を参照
- OHLCVデータはBaseDataSource経由で取得
- 成行注文の約定価格はCostConfig.market_fill_price_typeで選択

---

## Phase 6: Exchange Clients Package Setup

**Purpose**: exchange_clientsパッケージの初期化

- [x] T121 src/qeel/exchange_clients/__init__.pyを作成（パッケージ初期化）

**Checkpoint**: パッケージ構造完成

---

## Phase 7: BaseExchangeClient ABC

**Purpose**: 取引所クライアント抽象基底クラスの実装（contracts/base_exchange_client.md参照）

### Tests (TDD: RED)

- [x] T122 tests/unit/test_exchange_clients.pyを新規作成
  - `test_base_exchange_client_cannot_instantiate`: ABCは直接インスタンス化不可
  - `test_base_exchange_client_has_abstract_methods`: submit_orders, fetch_fills, fetch_positionsが抽象メソッド

### Implementation (TDD: GREEN)

- [x] T123 src/qeel/exchange_clients/base.pyにBaseExchangeClient ABCを実装
  - `_validate_orders(orders: pl.DataFrame) -> None`: OrderSchemaバリデーションヘルパー
  - `_validate_fills(fills: pl.DataFrame) -> pl.DataFrame`: FillReportSchemaバリデーションヘルパー
  - `_validate_positions(positions: pl.DataFrame) -> pl.DataFrame`: PositionSchemaバリデーションヘルパー
  - `submit_orders(orders: pl.DataFrame) -> None`: 抽象メソッド
  - `fetch_fills(start: datetime, end: datetime) -> pl.DataFrame`: 抽象メソッド
  - `fetch_positions() -> pl.DataFrame`: 抽象メソッド

**Checkpoint**: `uv run pytest tests/unit/test_exchange_clients.py -k "base"` 全件パス

---

## Phase 8: MockExchangeClient - 基盤実装

**Purpose**: バックテスト用モック取引所クライアントの基盤実装

### Tests (TDD: RED)

- [x] T124 tests/unit/test_exchange_clients.pyにTestMockExchangeClientBaseクラスを追加
  - `test_mock_exchange_client_init`: 正常に初期化される（CostConfig, BaseDataSourceを受け取る）
  - `test_mock_exchange_client_init_stores_data_source`: ohlcv_data_source属性にBaseDataSourceインスタンスが保持される
  - `test_mock_exchange_client_load_ohlcv`: OHLCVデータをキャッシュする
  - `test_mock_exchange_client_load_ohlcv_calls_fetch`: load_ohlcv()がBaseDataSource.fetch()を呼び出すことを確認
  - `test_mock_exchange_client_set_current_datetime`: 現在のiteration日時を設定する
  - `test_mock_exchange_client_get_next_bar`: 翌バーのOHLCVを取得する
  - `test_mock_exchange_client_get_current_bar`: 当バーのOHLCVを取得する

### Implementation (TDD: GREEN)

- [x] T125 src/qeel/exchange_clients/mock.pyにMockExchangeClient基盤を実装
  - `__init__(config: CostConfig, ohlcv_data_source: BaseDataSource)`
  - `load_ohlcv(start: datetime, end: datetime, symbols: list[str]) -> None`
  - `set_current_datetime(dt: datetime) -> None`
  - `_get_next_bar(symbol: str) -> pl.DataFrame | None`
  - `_get_current_bar(symbol: str) -> pl.DataFrame | None`
  - `ohlcv_cache`、`current_datetime`、`pending_fills`、`fill_history`属性

**Checkpoint**: `uv run pytest tests/unit/test_exchange_clients.py -k "mock"` 全件パス

---

## Phase 9: MockExchangeClient - スリッページ計算

**Purpose**: スリッページ計算ロジックの実装

### Tests (TDD: RED)

- [x] T126 tests/unit/test_exchange_clients.pyにTestMockExchangeClientSlippageクラスを追加
  - `test_apply_slippage_buy_increases_price`: 買い注文でスリッページ適用後、価格が上昇する
  - `test_apply_slippage_sell_decreases_price`: 売り注文でスリッページ適用後、価格が下落する
  - `test_apply_slippage_zero_bps_no_change`: スリッページ0bpsの場合、価格変化なし
  - `test_apply_slippage_calculation_formula`: 計算式が正しい（price * (1 ± slippage_bps/10000)）

### Implementation (TDD: GREEN)

- [x] T127 src/qeel/exchange_clients/mock.pyに`_apply_slippage`メソッドを実装
  - `_apply_slippage(price: float, side: str) -> float`
  - 買い: +slippage（不利方向=高く買う）
  - 売り: -slippage（不利方向=安く売る）

**Checkpoint**: `uv run pytest tests/unit/test_exchange_clients.py -k "slippage"` 全件パス

---

## Phase 10: MockExchangeClient - 成行注文処理

**Purpose**: 成行注文の約定処理ロジック実装

### Tests (TDD: RED)

- [x] T128 tests/unit/test_exchange_clients.pyにTestMockExchangeClientMarketOrderクラスを追加
  - `test_process_market_order_next_open_price`: market_fill_price_type="next_open"で翌バーのopenで約定
  - `test_process_market_order_current_close_price`: market_fill_price_type="current_close"で当バーのcloseで約定
  - `test_process_market_order_applies_slippage`: スリッページが適用される
  - `test_process_market_order_calculates_commission`: 手数料が正しく計算される（filled_price * quantity * commission_rate）
  - `test_process_market_order_returns_none_when_no_next_bar`: 翌バーがない場合Noneを返す
  - `test_process_market_order_fill_structure`: 約定情報の構造が正しい（order_id, symbol, side, filled_quantity, filled_price, commission, timestamp）
  - `test_process_market_order_last_bar_multiple_orders`: 最終バー付近で複数注文を実行した場合、翌バーがない注文のみNoneを返す（部分約定シナリオ）

### Implementation (TDD: GREEN)

- [x] T129 src/qeel/exchange_clients/mock.pyに`_process_market_order`メソッドを実装
  - `_process_market_order(symbol: str, side: str, quantity: float) -> dict | None`
  - CostConfig.market_fill_price_typeに基づき約定価格を決定
  - スリッページ適用、手数料計算

**Checkpoint**: `uv run pytest tests/unit/test_exchange_clients.py -k "market_order"` 全件パス

---

## Phase 11: MockExchangeClient - 指値注文処理

**Purpose**: 指値注文の約定判定ロジック実装

### Tests (TDD: RED)

- [x] T130 tests/unit/test_exchange_clients.pyにTestMockExchangeClientLimitOrderクラスを追加
  - `test_process_limit_order_buy_fills_when_price_above_low`: 買い指値が翌バーのlowより高い場合約定
  - `test_process_limit_order_buy_not_fills_when_price_equals_low`: 買い指値が翌バーのlowと同値の場合未約定
  - `test_process_limit_order_sell_fills_when_price_below_high`: 売り指値が翌バーのhighより低い場合約定
  - `test_process_limit_order_sell_not_fills_when_price_equals_high`: 売り指値が翌バーのhighと同値の場合未約定
  - `test_process_limit_order_fills_at_limit_price`: 約定価格は指値価格そのもの（スリッページなし）
  - `test_process_limit_order_calculates_commission`: 手数料が正しく計算される
  - `test_process_limit_order_returns_none_when_no_next_bar`: 翌バーがない場合Noneを返す
  - `test_process_limit_order_float_comparison_edge_case`: 浮動小数点比較で同値判定が正しく動作する（例: 100.0 == 100.0は未約定、100.01 > 100.0は約定）

### Implementation (TDD: GREEN)

- [x] T131 src/qeel/exchange_clients/mock.pyに`_process_limit_order`メソッドを実装
  - `_process_limit_order(symbol: str, side: str, quantity: float, limit_price: float) -> dict | None`
  - 翌バーのhigh/lowで約定判定
  - 同値は未約定

**Checkpoint**: `uv run pytest tests/unit/test_exchange_clients.py -k "limit_order"` 全件パス

---

## Phase 12: MockExchangeClient - submit_orders

**Purpose**: 注文執行メソッドの実装

### Tests (TDD: RED)

- [x] T132 tests/unit/test_exchange_clients.pyにTestMockExchangeClientSubmitOrdersクラスを追加
  - `test_submit_orders_validates_schema`: OrderSchemaバリデーションが実行される
  - `test_submit_orders_processes_market_orders`: 成行注文が正しく処理される
  - `test_submit_orders_processes_limit_orders`: 指値注文が正しく処理される
  - `test_submit_orders_processes_mixed_orders`: 成行と指値の混合注文が処理される
  - `test_submit_orders_stores_fills_in_pending`: 約定情報がpending_fillsに追加される
  - `test_submit_orders_stores_fills_in_history`: 約定情報がfill_historyに追加される
  - `test_submit_orders_raises_on_limit_without_price`: 指値注文でpriceがNoneの場合ValueError

### Implementation (TDD: GREEN)

- [x] T133 src/qeel/exchange_clients/mock.pyに`submit_orders`メソッドを実装
  - `submit_orders(orders: pl.DataFrame) -> None`
  - `_validate_orders`を使用してスキーマバリデーション
  - 各注文をiter_rowsで処理し、市場/指値を振り分け
  - 約定情報をpending_fillsとfill_historyに追加

**Checkpoint**: `uv run pytest tests/unit/test_exchange_clients.py -k "submit_orders"` 全件パス

---

## Phase 13: MockExchangeClient - fetch_fills

**Purpose**: 期間指定による約定情報取得メソッドの実装

### Tests (TDD: RED)

- [x] T134 tests/unit/test_exchange_clients.pyにTestMockExchangeClientFetchFillsクラスを追加
  - `test_fetch_fills_returns_empty_when_no_fills`: 約定がない場合空DataFrameを返す
  - `test_fetch_fills_returns_fills_in_range`: 指定期間内の約定のみを返す
  - `test_fetch_fills_can_fetch_multiple_times`: 同じ期間を何度でも取得可能
  - `test_fetch_fills_validates_schema`: FillReportSchemaバリデーションが実行される
  - `test_fetch_fills_schema_compliance`: 返却DataFrameがFillReportSchemaに準拠

### Implementation (TDD: GREEN)

- [x] T135 src/qeel/exchange_clients/mock.pyに`fetch_fills`メソッドを実装
  - `fetch_fills(start: datetime, end: datetime) -> pl.DataFrame`
  - fill_historyから期間でフィルタして返却
  - 何度でも同じ期間の約定を取得可能
  - `_validate_fills`でスキーマバリデーション

**Checkpoint**: `uv run pytest tests/unit/test_exchange_clients.py -k "fetch_fills"` 全件パス

---

## Phase 14: MockExchangeClient - fetch_positions

**Purpose**: ポジション取得メソッドの実装

### Tests (TDD: RED)

- [x] T136 tests/unit/test_exchange_clients.pyにTestMockExchangeClientFetchPositionsクラスを追加
  - `test_fetch_positions_returns_empty_when_no_history`: 約定履歴がない場合空DataFrameを返す
  - `test_fetch_positions_calculates_from_buys`: 買い約定からポジション数量を計算
  - `test_fetch_positions_calculates_from_sells`: 売り約定でポジション数量が減少
  - `test_fetch_positions_calculates_avg_price`: 平均取得単価を正しく計算（買いの加重平均）
  - `test_fetch_positions_excludes_zero_positions`: 数量ゼロのポジションは除外
  - `test_fetch_positions_handles_multiple_symbols`: 複数銘柄を正しく集計
  - `test_fetch_positions_validates_schema`: PositionSchemaバリデーションが実行される
  - `test_fetch_positions_allows_short_positions`: ショートポジション（マイナス数量）を許容し、正しく返す
  - `test_fetch_positions_short_avg_price_calculation`: ショートポジションの平均取得単価は売りの加重平均

### Implementation (TDD: GREEN)

- [x] T137 src/qeel/exchange_clients/mock.pyに`fetch_positions`メソッドを実装
  - `fetch_positions() -> pl.DataFrame`
  - fill_historyからポジションを累積計算
  - 買いは+、売りは-として数量を符号付きに
  - ショートポジション（マイナス数量）を許容
  - 平均取得単価: ロングは買いの加重平均、ショートは売りの加重平均
  - 数量ゼロのポジションは除外
  - `_validate_positions`でスキーマバリデーション

**Checkpoint**: `uv run pytest tests/unit/test_exchange_clients.py -k "fetch_positions"` 全件パス

---

## Phase 15: Module Exports

**Purpose**: モジュールエクスポートの設定

- [x] T138 src/qeel/exchange_clients/__init__.pyにBaseExchangeClient, MockExchangeClientをエクスポート
- [x] T139 src/qeel/__init__.pyにexchange_clientsモジュールを追加

**Checkpoint**: `from qeel.exchange_clients import BaseExchangeClient, MockExchangeClient` が成功

---

## Phase 16: Integration Tests

**Purpose**: 統合テストの作成

### Tests

- [x] T140 tests/integration/test_exchange_client_integration.pyを新規作成
  - `test_mock_exchange_client_full_workflow`: load_ohlcv → set_current_datetime → submit_orders → fetch_fills → fetch_positions の一連のフロー
  - `test_mock_exchange_client_multiple_iterations`: 複数iterationでのポジション累積
  - `test_mock_exchange_client_with_parquet_data_source`: ParquetDataSourceと連携したテスト

**Checkpoint**: `uv run pytest tests/integration/test_exchange_client_integration.py` 全件パス

---

## Phase 17: Quality Assurance for 007

**Purpose**: 品質チェックと最終確認

- [x] T141 `uv run mypy src/qeel/exchange_clients/` で型エラーゼロを確認
- [x] T142 `uv run ruff check src/qeel/exchange_clients/` でリンターエラーゼロを確認
- [x] T143 [P] `uv run ruff format src/qeel/exchange_clients/` でフォーマット適用
- [x] T144 `uv run pytest tests/` で全テストパス（006までのテストも含む）

**Final Checkpoint**: 007ブランチ実装完了、008ブランチ（portfolio-and-orders）に進行可能

---

## Dependencies (007本体)

```
007-prerequisites (T105-T120) 完了
     ↓
T121 (Package Setup)
     ↓
T122 → T123 (BaseExchangeClient ABC)
     ↓
T124 → T125 (MockExchangeClient基盤)
     ↓
T126 → T127 (スリッページ計算)
     ↓
T128 → T129 (成行注文処理)
     ↓
T130 → T131 (指値注文処理)
     ↓
T132 → T133 (submit_orders)
     ↓
T134 → T135 (fetch_fills)
     ↓
T136 → T137 (fetch_positions)
     ↓
T138, T139 (Module Exports) - 並列実行可能
     ↓
T140 (Integration Tests)
     ↓
T141, T142, T143, T144 (品質ゲート) - T141, T142, T143は並列実行可能
```

## Parallel Execution Opportunities (007本体)

- Phase 6内のT121は単独
- Phase 7-14は順序依存あり（TDD: RED→GREEN）
- Phase 15のT138, T139は並列実行可能
- Phase 17のT141, T142, T143は並列実行可能

---

## Task Summary (007本体)

- **Total Tasks (007本体)**: 24 (T121-T144)
- **Package Setup Tasks**: 1
- **BaseExchangeClient Tasks**: 2 (tests + impl)
- **MockExchangeClient基盤Tasks**: 2 (tests + impl)
- **スリッページ計算Tasks**: 2 (tests + impl)
- **成行注文処理Tasks**: 2 (tests + impl)
- **指値注文処理Tasks**: 2 (tests + impl)
- **submit_orders Tasks**: 2 (tests + impl)
- **fetch_fills Tasks**: 2 (tests + impl)
- **fetch_positions Tasks**: 2 (tests + impl)
- **Module Exports Tasks**: 2
- **Integration Tasks**: 1
- **QA Tasks**: 4

---

## Implementation Strategy (007本体)

### MVP (最小実装)

1. Phase 6: Package Setup完了
2. Phase 7: BaseExchangeClient ABC完了
3. Phase 8-9: MockExchangeClient基盤 + スリッページ完了
4. Phase 10: 成行注文処理完了
5. Phase 12-13: submit_orders + fetch_fills完了
6. Phase 17: QA実行

この時点で成行注文のバックテストが可能

### Full Implementation

1. MVP完了後
2. Phase 11: 指値注文処理完了
3. Phase 14: fetch_positions完了
4. Phase 15: Module Exports完了
5. Phase 16: Integration Tests完了
6. Phase 17: 最終QA

---

## Notes (007本体)

- contracts/base_exchange_client.mdの仕様に厳密に準拠
- data-model.md 2.4-2.6のスキーマ定義を参照
- OHLCVデータはBaseDataSource経由で取得（一貫したデータアクセス）
- 成行注文の約定価格はCostConfig.market_fill_price_typeで選択
- 指値注文の同値判定は未約定（より保守的な実装、浮動小数点は直接比較 `==` を使用）
- 手数料は約定価格ベースで計算（注文価格ではない）
- **ショートポジション（マイナス数量）を許容**: 売り約定が買い約定を上回る場合、負の数量で表現
- **market_impact_modelは007スコープ外**: CostConfigに定義はあるが、MockExchangeClientでは使用しない（将来ブランチで対応）
- 日本語コメント・docstring必須（constitution準拠）
- 各フェーズ完了後に品質ゲートチェック（mypy, ruff, pytest）

---

## Dependencies (007全体: prerequisites + 本体)

```
006-io-and-context-management (完了)
            ↓
    007-prerequisites (T105-T120) ← 完了済み
            ↓
    007-本体 (T121-T144)
```

## Parallel Execution Opportunities (007全体)

- prerequisites (T105-T120) は完了済み
- 本体 (T121-T144) に集中
- Phase 15のT138, T139は並列実行可能
- Phase 17のT141, T142, T143は並列実行可能

---

