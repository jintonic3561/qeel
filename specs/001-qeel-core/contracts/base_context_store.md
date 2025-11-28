# Contract: BaseContextStore

## 概要

コンテキスト（ポジション、選択銘柄、モデルパラメータ等）の保存・読み込みを抽象化するインターフェース。バックテスト時はローカルファイル、実運用時はS3やデータベースを使用する。

## インターフェース定義

```python
from abc import ABC, abstractmethod
from qeel.models import Context

class BaseContextStore(ABC):
    """コンテキスト永続化抽象基底クラス

    iteration間でコンテキストを保存・復元する。
    """

    @abstractmethod
    def save(self, context: Context) -> None:
        """コンテキストを保存する

        Args:
            context: 保存するコンテキスト

        Raises:
            RuntimeError: 保存失敗時
        """
        ...

    @abstractmethod
    def load(self) -> Context | None:
        """コンテキストを読み込む

        Returns:
            保存されたコンテキスト。存在しない場合はNone

        Raises:
            RuntimeError: 読み込み失敗時（破損など）
        """
        ...

    @abstractmethod
    def exists(self) -> bool:
        """コンテキストが存在するか確認

        Returns:
            コンテキストが保存されている場合True
        """
        ...
```

## 実装例

### ローカルファイル保存（JSON/Parquet対応）

```python
from pathlib import Path
import json
import polars as pl
from typing import Literal
from qeel.stores import BaseContextStore
from qeel.models import Context

class LocalStore(BaseContextStore):
    """ローカルファイルにコンテキストを保存（JSON/Parquet両対応）"""

    def __init__(self, path: Path, format: Literal["json", "parquet"] = "json"):
        """
        Args:
            path: 保存先パス（JSONの場合はファイルパス、Parquetの場合はディレクトリパス）
            format: 保存フォーマット（"json" または "parquet"）
        """
        self.path = path
        self.format = format

        if format == "parquet":
            self.meta_path = path / "context_meta.json"
            self.positions_path = path / "positions.parquet"

    def save(self, context: Context) -> None:
        try:
            if self.format == "json":
                # JSON形式で保存（DataFrameをdictに変換）
                data = {
                    "current_datetime": context.current_datetime.isoformat(),
                    "signals": context.signals.to_dict(as_series=False) if context.signals is not None else None,
                    "portfolio_plan": context.portfolio_plan.to_dict(as_series=False) if context.portfolio_plan is not None else None,
                    "orders": context.orders.to_dict(as_series=False) if context.orders is not None else None,
                    "positions": context.positions.to_dict(as_series=False) if context.positions is not None else None,
                }
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

            elif self.format == "parquet":
                # Parquet + JSON形式で保存
                self.path.mkdir(parents=True, exist_ok=True)

                # DataFrameをParquetで保存
                if context.signals is not None:
                    context.signals.write_parquet(self.path / "signals.parquet")
                if context.portfolio_plan is not None:
                    context.portfolio_plan.write_parquet(self.path / "portfolio_plan.parquet")
                if context.orders is not None:
                    context.orders.write_parquet(self.path / "orders.parquet")
                if context.positions is not None:
                    context.positions.write_parquet(self.path / "positions.parquet")

                # その他のメタデータをJSONで保存
                meta = {
                    "current_datetime": context.current_datetime.isoformat(),
                    "has_signals": context.signals is not None,
                    "has_portfolio_plan": context.portfolio_plan is not None,
                    "has_orders": context.orders is not None,
                    "has_positions": context.positions is not None,
                }
                with open(self.meta_path, 'w', encoding='utf-8') as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2)

        except Exception as e:
            raise RuntimeError(f"コンテキスト保存エラー: {e}")

    def load(self) -> Context | None:
        if not self.exists():
            return None

        try:
            if self.format == "json":
                # JSON形式から読み込み（dictをDataFrameに変換）
                with open(self.path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                return Context(
                    current_datetime=datetime.fromisoformat(data["current_datetime"]),
                    signals=pl.DataFrame(data["signals"]) if data.get("signals") else None,
                    portfolio_plan=pl.DataFrame(data["portfolio_plan"]) if data.get("portfolio_plan") else None,
                    orders=pl.DataFrame(data["orders"]) if data.get("orders") else None,
                    positions=pl.DataFrame(data["positions"]) if data.get("positions") else None,
                )

            elif self.format == "parquet":
                # Parquet + JSON形式から読み込み
                with open(self.meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)

                signals_df = pl.read_parquet(self.path / "signals.parquet") if meta.get("has_signals") else None
                portfolio_plan_df = pl.read_parquet(self.path / "portfolio_plan.parquet") if meta.get("has_portfolio_plan") else None
                orders_df = pl.read_parquet(self.path / "orders.parquet") if meta.get("has_orders") else None
                positions_df = pl.read_parquet(self.path / "positions.parquet") if meta.get("has_positions") else None

                return Context(
                    current_datetime=datetime.fromisoformat(meta["current_datetime"]),
                    signals=signals_df,
                    portfolio_plan=portfolio_plan_df,
                    orders=orders_df,
                    positions=positions_df,
                )

        except Exception as e:
            raise RuntimeError(f"コンテキスト読み込みエラー: {e}")

    def exists(self) -> bool:
        if self.format == "json":
            return self.path.exists()
        elif self.format == "parquet":
            # メタデータファイルの存在のみチェック（個別のParquetファイルはオプション）
            return self.meta_path.exists()
        return False
```

### S3保存（実運用必須対応、JSON/Parquet対応）

```python
import boto3
import json
import polars as pl
from io import BytesIO
from typing import Literal
from qeel.stores import BaseContextStore
from qeel.models import Context

class S3Store(BaseContextStore):
    """S3にコンテキストを保存（JSON/Parquet両対応、実運用必須）"""

    def __init__(self, bucket: str, key_prefix: str, format: Literal["json", "parquet"] = "json"):
        """
        Args:
            bucket: S3バケット名
            key_prefix: S3キーのプレフィックス
            format: 保存フォーマット（"json" または "parquet"）
        """
        self.bucket = bucket
        self.key_prefix = key_prefix
        self.format = format
        self.s3_client = boto3.client('s3')

    def save(self, context: Context) -> None:
        try:
            if self.format == "json":
                # JSON形式で保存（DataFrameをdictに変換）
                data = {
                    "current_datetime": context.current_datetime.isoformat(),
                    "signals": context.signals.to_dict(as_series=False) if context.signals is not None else None,
                    "portfolio_plan": context.portfolio_plan.to_dict(as_series=False) if context.portfolio_plan is not None else None,
                    "orders": context.orders.to_dict(as_series=False) if context.orders is not None else None,
                    "positions": context.positions.to_dict(as_series=False) if context.positions is not None else None,
                }
                key = f"{self.key_prefix}/context.json"
                self.s3_client.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=json.dumps(data, ensure_ascii=False),
                )

            elif self.format == "parquet":
                # Parquet + JSON形式で保存
                # DataFrameをParquetで保存
                if context.signals is not None:
                    buffer = BytesIO()
                    context.signals.write_parquet(buffer)
                    buffer.seek(0)
                    self.s3_client.put_object(
                        Bucket=self.bucket,
                        Key=f"{self.key_prefix}/signals.parquet",
                        Body=buffer.getvalue(),
                    )

                if context.portfolio_plan is not None:
                    buffer = BytesIO()
                    context.portfolio_plan.write_parquet(buffer)
                    buffer.seek(0)
                    self.s3_client.put_object(
                        Bucket=self.bucket,
                        Key=f"{self.key_prefix}/portfolio_plan.parquet",
                        Body=buffer.getvalue(),
                    )

                if context.orders is not None:
                    buffer = BytesIO()
                    context.orders.write_parquet(buffer)
                    buffer.seek(0)
                    self.s3_client.put_object(
                        Bucket=self.bucket,
                        Key=f"{self.key_prefix}/orders.parquet",
                        Body=buffer.getvalue(),
                    )

                if context.positions is not None:
                    buffer = BytesIO()
                    context.positions.write_parquet(buffer)
                    buffer.seek(0)
                    self.s3_client.put_object(
                        Bucket=self.bucket,
                        Key=f"{self.key_prefix}/positions.parquet",
                        Body=buffer.getvalue(),
                    )

                # その他のメタデータをJSONで保存
                meta = {
                    "current_datetime": context.current_datetime.isoformat(),
                    "has_signals": context.signals is not None,
                    "has_portfolio_plan": context.portfolio_plan is not None,
                    "has_orders": context.orders is not None,
                    "has_positions": context.positions is not None,
                }
                meta_key = f"{self.key_prefix}/context_meta.json"
                self.s3_client.put_object(
                    Bucket=self.bucket,
                    Key=meta_key,
                    Body=json.dumps(meta, ensure_ascii=False),
                )

        except Exception as e:
            raise RuntimeError(f"S3保存エラー: {e}")

    def load(self) -> Context | None:
        try:
            if self.format == "json":
                # JSON形式から読み込み（dictをDataFrameに変換）
                key = f"{self.key_prefix}/context.json"
                response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
                data = json.loads(response['Body'].read().decode('utf-8'))

                return Context(
                    current_datetime=datetime.fromisoformat(data["current_datetime"]),
                    signals=pl.DataFrame(data["signals"]) if data.get("signals") else None,
                    portfolio_plan=pl.DataFrame(data["portfolio_plan"]) if data.get("portfolio_plan") else None,
                    orders=pl.DataFrame(data["orders"]) if data.get("orders") else None,
                    positions=pl.DataFrame(data["positions"]) if data.get("positions") else None,
                )

            elif self.format == "parquet":
                # Parquet + JSON形式から読み込み
                meta_key = f"{self.key_prefix}/context_meta.json"
                meta_response = self.s3_client.get_object(Bucket=self.bucket, Key=meta_key)
                meta = json.loads(meta_response['Body'].read().decode('utf-8'))

                signals_df = None
                if meta.get("has_signals"):
                    signals_response = self.s3_client.get_object(Bucket=self.bucket, Key=f"{self.key_prefix}/signals.parquet")
                    signals_df = pl.read_parquet(BytesIO(signals_response['Body'].read()))

                portfolio_plan_df = None
                if meta.get("has_portfolio_plan"):
                    portfolio_response = self.s3_client.get_object(Bucket=self.bucket, Key=f"{self.key_prefix}/portfolio_plan.parquet")
                    portfolio_plan_df = pl.read_parquet(BytesIO(portfolio_response['Body'].read()))

                orders_df = None
                if meta.get("has_orders"):
                    orders_response = self.s3_client.get_object(Bucket=self.bucket, Key=f"{self.key_prefix}/orders.parquet")
                    orders_df = pl.read_parquet(BytesIO(orders_response['Body'].read()))

                positions_df = None
                if meta.get("has_positions"):
                    positions_response = self.s3_client.get_object(Bucket=self.bucket, Key=f"{self.key_prefix}/positions.parquet")
                    positions_df = pl.read_parquet(BytesIO(positions_response['Body'].read()))

                return Context(
                    current_datetime=datetime.fromisoformat(meta["current_datetime"]),
                    signals=signals_df,
                    portfolio_plan=portfolio_plan_df,
                    orders=orders_df,
                    positions=positions_df,
                )

        except self.s3_client.exceptions.NoSuchKey:
            return None
        except Exception as e:
            raise RuntimeError(f"S3読み込みエラー: {e}")

    def exists(self) -> bool:
        try:
            if self.format == "json":
                key = f"{self.key_prefix}/context.json"
                self.s3_client.head_object(Bucket=self.bucket, Key=key)
                return True

            elif self.format == "parquet":
                # メタデータファイルの存在のみチェック（個別のParquetファイルはオプション）
                meta_key = f"{self.key_prefix}/context_meta.json"
                self.s3_client.head_object(Bucket=self.bucket, Key=meta_key)
                return True

        except self.s3_client.exceptions.NoSuchKey:
            return False
```

## 契約事項

### save

- 入力: `Context` Pydanticモデル
- 既存のコンテキストは上書き
- 保存失敗時はRuntimeErrorをraise

### load

- 出力: 保存された `Context` またはNone
- コンテキストが存在しない場合はNoneを返す
- 破損している場合はRuntimeErrorをraise

### exists

- コンテキストの存在チェック
- 高速に動作すること（実際の読み込みは行わない）

## テスタビリティ

- `InMemoryStore` をテスト用に実装可能:

```python
class InMemoryStore(BaseContextStore):
    def __init__(self):
        self._context: Context | None = None

    def save(self, context: Context) -> None:
        self._context = context

    def load(self) -> Context | None:
        return self._context

    def exists(self) -> bool:
        return self._context is not None
```

## 標準実装

Qeelは以下の標準実装を提供する：

- `LocalStore`: ローカルファイル保存（JSON/Parquet両対応、バックテスト用）
  - `LocalStore(path, format="json")`: JSON形式
  - `LocalStore(path, format="parquet")`: Parquet + JSON形式
- `S3Store`: S3保存（JSON/Parquet両対応、**実運用必須対応**、Branch 005で実装）
  - `S3Store(bucket, key_prefix, format="json")`: JSON形式
  - `S3Store(bucket, key_prefix, format="parquet")`: Parquet + JSON形式
- `InMemoryStore`: テスト用インメモリ保存

ユーザは独自実装（データベース、他のクラウドストレージ等）を自由に追加可能。
