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
            return S3IO(
                strategy_name=general_config.strategy_name,
                bucket=general_config.s3_bucket,
                region=general_config.s3_region,
            )
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

    @abstractmethod
    def list_files(self, path: str, pattern: str | None = None) -> list[str]:
        """指定パス配下のファイル一覧を取得する

        Args:
            path: 検索対象ディレクトリパス（LocalIOの場合はローカルパス、S3IOの場合はキープレフィックス）
            pattern: ファイル名のフィルタパターン（例: "signals_*.parquet"）。Noneの場合は全ファイル

        Returns:
            マッチしたファイルパスのリスト（フルパス）。存在しない場合は空リスト
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

    def _is_glob_pattern(self, path: str) -> bool:
        """パスがglobパターンを含むか判定"""
        return "*" in path or "?" in path or "[" in path

    def load(self, path: str, format: str) -> dict | pl.DataFrame | None:
        """ローカルファイルから読み込み

        parquet形式の場合、globパターン（*, ?, []）をサポート。
        Polarsのread_parquetに直接委譲し、複数ファイルの自動結合やHiveパーティショニングに対応。
        """
        is_glob = self._is_glob_pattern(path)

        if format == "json":
            file_path = Path(path)
            if not file_path.exists():
                return None
            import json
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        elif format == "parquet":
            # globパターンの場合は存在チェックをスキップし、Polarsに委譲
            if not is_glob:
                file_path = Path(path)
                if not file_path.exists():
                    return None
            # Polarsはglobパターン、Hiveパーティショニングをネイティブサポート
            return pl.read_parquet(path)
        else:
            raise ValueError(f"サポートされていないフォーマット: {format}")

    def exists(self, path: str) -> bool:
        """ファイルの存在確認"""
        return Path(path).exists()

    def list_files(self, path: str, pattern: str | None = None) -> list[str]:
        """指定パス配下のファイル一覧を取得"""
        import fnmatch

        dir_path = Path(path)
        if not dir_path.exists():
            return []

        files = [str(f) for f in dir_path.rglob("*") if f.is_file()]
        if pattern:
            files = [f for f in files if fnmatch.fnmatch(Path(f).name, pattern)]
        return sorted(files)
```

### S3IO（S3ストレージ）

```python
from datetime import datetime
from io import BytesIO

import boto3
import polars as pl

from qeel.io.base import BaseIO


class S3IO(BaseIO):
    """S3ストレージIO実装

    parquet形式の読み込みはPolarsのネイティブS3サポートを使用し、
    globパターンやHiveパーティショニングに対応。
    """

    def __init__(self, strategy_name: str, bucket: str, region: str):
        self.strategy_name = strategy_name
        self.bucket = bucket
        self.region = region
        self.s3_client = boto3.client('s3', region_name=region)
        # PolarsのネイティブS3読み込み用storage_options
        self._storage_options = {"aws_region": region}

    def get_base_path(self, subdir: str) -> str:
        """S3キープレフィックスを返す（{strategy_name}/{subdir}/）"""
        return f"{self.strategy_name}/{subdir}"

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

    def _is_glob_pattern(self, path: str) -> bool:
        """パスがglobパターンを含むか判定"""
        return "*" in path or "?" in path or "[" in path

    def _to_s3_uri(self, path: str) -> str:
        """S3キーをs3://形式のURIに変換"""
        return f"s3://{self.bucket}/{path}"

    def load(self, path: str, format: str) -> dict | pl.DataFrame | None:
        """S3から読み込み

        parquet形式の場合、PolarsのネイティブS3サポートを使用し、
        globパターン（*, ?, []）やHiveパーティショニングに対応。
        """
        if format == "json":
            try:
                response = self.s3_client.get_object(Bucket=self.bucket, Key=path)
                body = response['Body'].read()
                import json
                return json.loads(body.decode('utf-8'))
            except self.s3_client.exceptions.NoSuchKey:
                return None
        elif format == "parquet":
            # PolarsのネイティブS3サポートを使用（glob、Hiveパーティショニング対応）
            s3_uri = self._to_s3_uri(path)
            return pl.read_parquet(s3_uri, storage_options=self._storage_options)
        else:
            raise ValueError(f"サポートされていないフォーマット: {format}")

    def exists(self, path: str) -> bool:
        """S3オブジェクトの存在確認"""
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=path)
            return True
        except self.s3_client.exceptions.ClientError:
            return False

    def list_files(self, path: str, pattern: str | None = None) -> list[str]:
        """指定プレフィックス配下のオブジェクト一覧を取得"""
        import fnmatch

        paginator = self.s3_client.get_paginator('list_objects_v2')
        files: list[str] = []

        for page in paginator.paginate(Bucket=self.bucket, Prefix=path):
            for obj in page.get('Contents', []):
                key = obj['Key']
                if pattern:
                    filename = key.split('/')[-1]
                    if fnmatch.fnmatch(filename, pattern):
                        files.append(key)
                else:
                    files.append(key)

        return sorted(files)
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
- S3IO: `{strategy_name}/{subdir}`を返す（strategy_nameはGeneralConfigから取得）

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
- **parquet形式はglobパターン対応**: `*`, `?`, `[]`を含むパスをPolarsに直接委譲
  - 例: `data/*.parquet`, `data/**/*.parquet`, `year=202[0-5]/*.parquet`
  - Hiveパーティショニング（`year=2024/month=01/`形式）も自動認識
  - S3の場合は`s3://bucket/path`形式でPolarsのネイティブS3サポートを使用
- 単一ファイルが存在しない場合は例外をraiseせず、Noneを返す
- globパターンでマッチするファイルがない場合は空のDataFrameまたは例外（Polarsの挙動に依存）
- ファイルが破損している場合はRuntimeErrorをraise

### exists

- 入力: パス
- 出力: ファイルが存在する場合True
- 高速に動作すること（実際の読み込みは行わない）

### list_files

- 入力: 検索対象パス、ファイル名パターン（オプション）
- 出力: マッチしたファイルパスのリスト（フルパス）、存在しない場合は空リスト
- LocalIO: `Path.rglob()`で再帰的に検索
- S3IO: `list_objects_v2`のpaginatorで検索
- パターンは`fnmatch`形式（例: `"signals_*.parquet"`）

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

    def list_files(self, path: str, pattern: str | None = None) -> list[str]:
        """インメモリストレージからファイル一覧を取得"""
        import fnmatch

        files = [k for k in self.storage.keys() if k.startswith(path)]
        if pattern:
            files = [f for f in files if fnmatch.fnmatch(f.split('/')[-1], pattern)]
        return sorted(files)
```

## 標準実装

Qeelは以下の標準実装を提供する:

- `LocalIO()`: ローカルファイルシステム（ワークスペース配下）
- `S3IO(bucket, region, strategy_name)`: S3ストレージ
- `InMemoryIO()`: テスト用インメモリストレージ（Branch 006で実装）

ユーザは独自実装（GCS、Azure Blob等）を自由に追加可能。
