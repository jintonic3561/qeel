[概要]
ある金融市場に対し定量的なアプローチでシグナル（特徴量）を設計し、それらに基づいたトレードを行います。
このプロジェクトでは、分析から実運用へのシームレスな接続を可能とするバックテストライブラリを開発します。


[思想]
1. バックテストしたロジックを、完全な再現性を保って実運用に転用できる
2. 多少実行速度を犠牲にしても、再現性の担保やリークの防止を重視する
3. バックテストは本システムの外部でロジックを詳細に検証したあとに1度のみ行うことを想定する
4. 本システムの外部でのEDAおよび検証時の特徴量生成関数、銘柄フィルタ関数などを、再現性を保ちつつバックテストループにそのまま組み込めるようにする
5. イベントベースのループはスコープ外とし、固定幅(時間足、日足、週足等)のみを想定する
6. 実運用におけるAPI呼び出し等は、取引所等に応じてユーザが柔軟に拡張実装できるようにする


[機能要件]
- 各iterationで複数のdataとポジション等の状態を参照することができる
- 複数銘柄の日次トレードに対応できる
- 各iterationのdataは任意の自前のソースを、複数、かつ任意のwindowを取得して扱える
- dataはローソク足の他、決算情報など任意のwindowのデータがありうる
- dataはその日に実際に利用可能かを示すdatetime列を含む
- iteration内部では以下を分離して実装できる
	- データから銘柄選択と執行価格/量を決定するロジック
	- 執行
	- リターンシミュレート(バックテスト時のみ、returnを計算)
	- 取引日判定
- executeは、はじめから実運用を想定して実装できる
	- バックテスト時にはモックによって入れ替え可能
	- ポジション等の状態を取得する関数も入れ替え可能
	- 運用時の当日を指定して単一のiterationを回すことで、バックテストと完全な再現性を持たせる
- 実運用結果とバックテスト結果の乖離を可視化できる
- 以下の設定をtomlで管理する
	- マーケットインパクト、スリッページ、手数料といったコスト
	- iterationのdata引数で受け取るデータソースのリスト
		- 各データで提供する過去window

[非機能要件]
- 必要十分な機能を有するシステムを最も効率よく開発する
- パッケージ化し、uvでpythonパッケージとしてローカルでインストールできるようにする

[設計イメージ]
- 設計イメージ（バックテスト）
    1. toml設定
        1. データごとのパラメータ管理
            - 日付判定カラム
            - ループ日付から差し引く時間（available_at）
                - ループ内ステップごとに定義
            - 提供window
        2. ループ管理
            - 各ステップが呼ばれるタイミング
                - ex. 銘柄選択はclose前、執行はclose後などに対応
                - ループ日付からのtimedeltaで定義？
    2. ループの実行 date_t
        - 各ステップの引数
            - 利用可能なラグに基づいたpl.DataFrame群
            - context
                - 実運用時は各ステップが個別のコンテナで呼ばれることを想定
                - csvやjson, parquetから復元可能なステップ固有のmodel
                - 選択銘柄、ポジション情報など
                - DBへの保存と読み込みをサポート
                    - 運用時はS3など
                    - バックテスト時はローカルモック
        1. シグナル計算: calculate_signals(market_data) → pl.DataFrame(schema={“symbol”: str, “signal”: float})
            - シグナルの計算に集中
            - override前提
        2. 銘柄選定: select_symbols(context(signals, positions)) → pl.DataFrame(schema={”symbol”: str, “signal”: float})
            - フィルタ、ポートフォリオ選択を含む
            - 単一銘柄にも対応
            - エントリーしない場合は空テーブル
            - override前提
        3. 執行条件計算: create_orders(context(market_data, selected_symbols, positions)) → pl.DataFrame(schema={”symbol”: str, “size”: float, “side”: str, “price”: float | None, “order_type”: Literal[”limit”, “market”]})
            - override前提
            - 数量、価格の最小単位丸めはバックテストと実運用でモック、API差し替え
            - モックの場合は丸めを行わない
        4. 執行: submit_orders(context(order_list)) → None
            - バックテスト時はモックで約定をシミュレートし、ローカルに保存
                - この部分は共通化し原則override不要
            - 運用時はAPI Client差し替え可能
                - override前提
    3. ループ終了後
        1. 約定情報取得: fetch_fill_reports → pl.DataFrame(schema={order_id: str, symbol: str, side: str, size: float, price: float, fee: float, timestamp: datetime})
            - リターン計算に必要な約定情報を取得
            - API互換になるように、共通のフォーマットで保持
            - バックテスト時はモック
                - この部分は共通化し原則override不要
            - 運用時はAPI Client差し替え可能
                - override前提
        2. パフォーマンス計算: calculate_metrics(fill_reports) → pl.DataFrame
            - 検証・運用時で全く同じロジックで成績を計算
            - 原則override不要
        3. 可視化: generate_performance_report(metrics_history) → None
            - 共通の成績データフォーマットが入力
            - 期間を指定すればバックテスト・実運用問わず共通のレポート出力可能
            - 分析フェーズの一括リターン計算ロジックによる系列とも比較し、問題がないか評価する
- 設計イメージ（分析）
    1. シグナル計算
        - バックテストループ内で呼び出す抽象クラスを定義する
        - このクラスを指定すればそのままバックテストが動くようにする
        - SignalBase(params: pydantic_model)
            - calculate_signals(market_data) → pl.DataFrameメソッドを必須化
                - 返り値のスキーマvalidation
    2. シグナル評価
        - 上記クラスを利用し、全期間のデータに対し一括でシグナル計算
        - 執行ロジックによるリターン計算抽象クラスを定義
        - 上記クラスによるリターン系列(pl.DataFrame(schema={datetime, symbol, return}), market_dataを引数にし、datetime, symbolで結合して評価を行う
        - 評価はシグナルとreturnとの順位相関係数とする
        - 評価は群で行い分布で出力する
            - Signalクラスのparamsに対し可能で網羅的なグリッドを作成し、それぞれで順位相関を評価
            - 年次など特定期間ごとの順位相関を評価
            - 上記の軸を個別/統合で分布で比較できるように可視化する
                - overfitを防ぎ、パラメータのチューニングに依存しないシグナル本体の強さを評価したい