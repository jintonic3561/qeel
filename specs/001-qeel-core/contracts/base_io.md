# Contract: BaseIO

## 概要

ファイル読み書きを抽象化するIOレイヤー。Local/S3の判別を一手に引き受け、ContextStoreとDataSourceはこのクラスを経由してデータ操作を行う。これにより、LocalStore/S3Storeの重複実装を排除し、DRY原則を遵守する。

## インターフェース定義

```python
from abc import ABC, abstractmethod
from datetime import datetime
from io import BytesIO
from pathlib import Path

import boto3
import polars as pl

from qeel.config import GeneralConfig
from qeel.utils import get_workspace


class BaseIO(ABC):
    """ファイル読み書きを抽象化するIOレイヤー

    Local/S3の判別を一手に引き受け、ContextStoreとDataSourceはこのクラスを経由してデータ操作を行う。
    """

    @classmethod
    def from_config(cls, general_config: GeneralConfig) -> "BaseIO":
        """General設定から適切なIO実装を返すファクトリメソッド

        Args:
            general_config: General設定

        Returns:
            storage_typeに応じたIO実装（LocalIOまたはS3IO）

        Raises:
            ValueError: storage_typeがサポートされていない場合、またはs3設定が不足している場合
        """
        if general_config.storage_type == "local":
            return LocalIO()
        elif general_config.storage_type == "s3":
            if general_config.s3_bucket is None or general_config.s3_region is None:
                raise ValueError("storage_type='s3'の場合、s3_bucketとs3_regionは必須です")
            return S3IO(bucket=general_config.s3_bucket, region=general_config.s3_region)
        else:
            raise ValueError(f"サポートされていないストレージタイプ: {general_config.storage_type}")

    @abstractmethod
    def get_base_path(self, subdir: str) -> str:
        """ベースパスを取得する

        Args:
            subdir: サブディレクトリ（"inputs"、"outputs"等）

        Returns:
            ベースパス文字列（ローカルパスまたはS3キープレフィックス）
        """
        ...

    @abstractmethod
    def get_partition_dir(self, base_path: str, target_datetime: datetime) -> str:
        """年月パーティショニングディレクトリを取得する

        Args:
            base_path: ベースパス
            target_datetime: パーティショニング対象の日時

        Returns:
            パーティションディレクトリパス（YYYY/MM/形式）
        """
        ...

    @abstractmethod
    def save(self, path: str, data: dict | pl.DataFrame, format: str) -> None:
        """データを保存する

        Args:
            path: 保存先パス（ベースパスからの相対パスまたは絶対パス）
            data: 保存するデータ（dictまたはDataFrame）
            format: フォーマット（"json"または"parquet"）

        Raises:
            ValueError: サポートされていないフォーマット、またはデータ型が不正な場合
            RuntimeError: 保存失敗時
        """
        ...

    @abstractmethod
    def load(self, path: str, format: str) -> dict | pl.DataFrame | None:
        """データを読み込む

        Args:
            path: 読み込み元パス（ベースパスからの相対パスまたは絶対パス）
            format: フォーマット（"json"または"parquet"）

        Returns:
            読み込んだデータ。存在しない場合はNone

        Raises:
            ValueError: サポートされていないフォーマット
            RuntimeError: 読み込み失敗時（破損など、ファイル不在以外）
        """
        ...

    @abstractmethod
    def exists(self, path: str) -> bool:
        """ファイルが存在するか確認する

        Args:
            path: 確認対象パス

        Returns:
            ファイルが存在する場合True
        """
        ...
```

## 実装例

### LocalIO（ローカルファイルシステム）

```python
from datetime import datetime
from pathlib import Path

import polars as pl

from qeel.io.base import BaseIO
from qeel.utils import get_workspace


class LocalIO(BaseIO):
    """ローカルファイルシステムIO実装"""

    def get_base_path(self, subdir: str) -> str:
        """ワークスペース配下のサブディレクトリパスを返す"""
        workspace = get_workspace()
        return str(workspace / subdir)

    def get_partition_dir(self, base_path: str, target_datetime: datetime) -> str:
        """年月パーティションディレクトリを返す（YYYY/MM/）"""
        partition_dir = Path(base_path) / target_datetime.strftime("%Y") / target_datetime.strftime("%m")
        partition_dir.mkdir(parents=True, exist_ok=True)
        return str(partition_dir)

    def save(self, path: str, data: dict | pl.DataFrame, format: str) -> None:
        """ローカルファイルに保存"""
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            import json
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        elif format == "parquet":
            if not isinstance(data, pl.DataFrame):
                raise ValueError("parquet形式の保存にはpl.DataFrameが必要です")
            data.write_parquet(file_path)
        else:
            raise ValueError(f"サポートされていないフォーマット: {format}")

    def load(self, path: str, format: str) -> dict | pl.DataFrame | None:
        """ローカルファイルから読み込み"""
        file_path = Path(path)
        if not file_path.exists():
            return None

        if format == "json":
            import json
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        elif format == "parquet":
            return pl.read_parquet(file_path)
        else:
            raise ValueError(f"サポートされていないフォーマット: {format}")

    def exists(self, path: str) -> bool:
        """ファイルの存在確認"""
        return Path(path).exists()
```

### S3IO（S3ストレージ）

```python
from datetime import datetime
from io import BytesIO

import boto3
import polars as pl

from qeel.io.base import BaseIO


class S3IO(BaseIO):
    """S3ストレージIO実装"""

    def __init__(self, bucket: str, region: str):
        self.bucket = bucket
        self.region = region
        self.s3_client = boto3.client('s3', region_name=region)

    def get_base_path(self, subdir: str) -> str:
        """S3キープレフィックスを返す（qeel/{subdir}/）"""
        return f"qeel/{subdir}"

    def get_partition_dir(self, base_path: str, target_datetime: datetime) -> str:
        """年月パーティションキープレフィックスを返す（YYYY/MM/）"""
        return f"{base_path}/{target_datetime.strftime('%Y')}/{target_datetime.strftime('%m')}"

    def save(self, path: str, data: dict | pl.DataFrame, format: str) -> None:
        """S3に保存"""
        if format == "json":
            import json
            body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        elif format == "parquet":
            if not isinstance(data, pl.DataFrame):
                raise ValueError("parquet形式の保存にはpl.DataFrameが必要です")
            buffer = BytesIO()
            data.write_parquet(buffer)
            buffer.seek(0)
            body = buffer.getvalue()
        else:
            raise ValueError(f"サポートされていないフォーマット: {format}")

        self.s3_client.put_object(Bucket=self.bucket, Key=path, Body=body)

    def load(self, path: str, format: str) -> dict | pl.DataFrame | None:
        """S3から読み込み"""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=path)
            body = response['Body'].read()

            if format == "json":
                import json
                return json.loads(body.decode('utf-8'))
            elif format == "parquet":
                buffer = BytesIO(body)
                return pl.read_parquet(buffer)
            else:
                raise ValueError(f"サポートされていないフォーマット: {format}")
        except self.s3_client.exceptions.NoSuchKey:
            return None

    def exists(self, path: str) -> bool:
        """S3オブジェクトの存在確認"""
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=path)
            return True
        except self.s3_client.exceptions.ClientError:
            return False
```

## 契約事項

### from_config

- 入力: `GeneralConfig`
- 出力: `storage_type`に応じた適切なIO実装（LocalIOまたはS3IO）
- storage_type="s3"の場合、s3_bucketとs3_regionが必須
- サポートされていないstorage_typeの場合はValueErrorをraise

### get_base_path

- 入力: サブディレクトリ名（"inputs"、"outputs"等）
- LocalIO: `$QEEL_WORKSPACE/{subdir}`を返す
- S3IO: `qeel/{subdir}`を返す

### get_partition_dir

- 入力: ベースパス、日時
- 年月でパーティショニング（YYYY/MM/形式）
- LocalIO: ディレクトリが存在しない場合は自動作成
- S3IO: プレフィックスのみ返す（S3はディレクトリの概念なし）

### save

- 入力: パス、データ（dictまたはDataFrame）、フォーマット（"json"または"parquet"）
- dict + json: UTF-8エンコードでJSON保存
- DataFrame + parquet: Parquet形式で保存
- 親ディレクトリが存在しない場合は自動作成（LocalIO）
- サポートされていないフォーマットまたはデータ型の場合はValueErrorをraise

### load

- 入力: パス、フォーマット（"json"または"parquet"）
- 出力: 読み込んだデータ（dictまたはDataFrame）、存在しない場合はNone
- ファイルが存在しない場合は例外をraiseせず、Noneを返す
- ファイルが破損している場合はRuntimeErrorをraise

### exists

- 入力: パス
- 出力: ファイルが存在する場合True
- 高速に動作すること（実際の読み込みは行わない）

## テスタビリティ

InMemoryIOをテスト用に実装可能:

```python
class InMemoryIO(BaseIO):
    """テスト用インメモリIO実装"""

    def __init__(self):
        self.storage: dict[str, dict | pl.DataFrame] = {}

    def get_base_path(self, subdir: str) -> str:
        return f"memory://{subdir}"

    def get_partition_dir(self, base_path: str, target_datetime: datetime) -> str:
        return f"{base_path}/{target_datetime.strftime('%Y')}/{target_datetime.strftime('%m')}"

    def save(self, path: str, data: dict | pl.DataFrame, format: str) -> None:
        self.storage[path] = data

    def load(self, path: str, format: str) -> dict | pl.DataFrame | None:
        return self.storage.get(path)

    def exists(self, path: str) -> bool:
        return path in self.storage
```

## 標準実装

Qeelは以下の標準実装を提供する:

- `LocalIO()`: ローカルファイルシステム（ワークスペース配下）
- `S3IO(bucket, region)`: S3ストレージ
- `InMemoryIO()`: テスト用インメモリストレージ（Branch 002で実装）

ユーザは独自実装（GCS、Azure Blob等）を自由に追加可能。
