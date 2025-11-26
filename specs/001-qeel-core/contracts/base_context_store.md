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

### ローカルファイル保存（JSON）

```python
from pathlib import Path
import json
from qeel.stores import BaseContextStore
from qeel.models import Context

class LocalJSONStore(BaseContextStore):
    """ローカルファイルにJSON形式でコンテキストを保存"""

    def __init__(self, file_path: Path):
        self.file_path = file_path

    def save(self, context: Context) -> None:
        try:
            # Pydanticモデル → dict → JSON
            data = context.model_dump(mode='json')
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise RuntimeError(f"コンテキスト保存エラー: {e}")

    def load(self) -> Context | None:
        if not self.exists():
            return None

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return Context(**data)
        except Exception as e:
            raise RuntimeError(f"コンテキスト読み込みエラー: {e}")

    def exists(self) -> bool:
        return self.file_path.exists()
```

### ローカルファイル保存（Parquet）

```python
import polars as pl
from pathlib import Path
from qeel.stores import BaseContextStore
from qeel.models import Context

class LocalParquetStore(BaseContextStore):
    """Positions DataFrameをParquetで保存、その他はJSON"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.meta_path = base_dir / "context_meta.json"
        self.positions_path = base_dir / "positions.parquet"

    def save(self, context: Context) -> None:
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)

            # Positions DataFrameをParquetで保存
            positions_df = context.get_positions_df()
            positions_df.write_parquet(self.positions_path)

            # その他のメタデータをJSONで保存
            meta = {
                "current_date": context.current_date.isoformat(),
                "selected_symbols": context.selected_symbols,
                "model_params": context.model_params,
            }
            with open(self.meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

        except Exception as e:
            raise RuntimeError(f"コンテキスト保存エラー: {e}")

    def load(self) -> Context | None:
        if not self.exists():
            return None

        try:
            # メタデータ読み込み
            with open(self.meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)

            # Positions読み込み
            positions_df = pl.read_parquet(self.positions_path)

            return Context.from_dataframe(
                current_date=datetime.fromisoformat(meta["current_date"]),
                positions_df=positions_df,
                selected_symbols=meta["selected_symbols"],
                model_params=meta["model_params"],
            )

        except Exception as e:
            raise RuntimeError(f"コンテキスト読み込みエラー: {e}")

    def exists(self) -> bool:
        return self.meta_path.exists() and self.positions_path.exists()
```

### S3保存（実運用用、ユーザ実装例）

```python
import boto3
import json
from qeel.stores import BaseContextStore
from qeel.models import Context

class S3Store(BaseContextStore):
    """S3にコンテキストを保存（実運用用）"""

    def __init__(self, bucket: str, key_prefix: str):
        self.bucket = bucket
        self.key_prefix = key_prefix
        self.s3_client = boto3.client('s3')

    def save(self, context: Context) -> None:
        try:
            data = context.model_dump(mode='json')
            key = f"{self.key_prefix}/context.json"
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json.dumps(data, ensure_ascii=False),
            )
        except Exception as e:
            raise RuntimeError(f"S3保存エラー: {e}")

    def load(self) -> Context | None:
        try:
            key = f"{self.key_prefix}/context.json"
            response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
            data = json.loads(response['Body'].read().decode('utf-8'))
            return Context(**data)
        except self.s3_client.exceptions.NoSuchKey:
            return None
        except Exception as e:
            raise RuntimeError(f"S3読み込みエラー: {e}")

    def exists(self) -> bool:
        try:
            key = f"{self.key_prefix}/context.json"
            self.s3_client.head_object(Bucket=self.bucket, Key=key)
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

Qeelは以下の標準実装を提供する予定：

- `LocalJSONStore`: ローカルJSON保存
- `LocalParquetStore`: ローカルParquet + JSON保存
- `InMemoryStore`: テスト用インメモリ保存

ユーザは独自実装（S3、データベース等）を自由に追加可能。
