"""S3IO実装

S3ストレージへのIO操作を提供する。
"""

import fnmatch
import json
from datetime import datetime
from io import BytesIO

import boto3
import polars as pl
from botocore.exceptions import ClientError

from qeel.io.base import BaseIO


class S3IO(BaseIO):
    """S3ストレージIO実装

    S3バケットに対してファイル読み書きを行う。
    """

    def __init__(self, bucket: str, region: str) -> None:
        """S3IOを初期化する

        Args:
            bucket: S3バケット名
            region: AWSリージョン
        """
        self.bucket = bucket
        self.region = region
        self.s3_client = boto3.client("s3", region_name=region)

    def get_base_path(self, subdir: str) -> str:
        """S3キープレフィックスを返す（qeel/{subdir}/）

        Args:
            subdir: サブディレクトリ名

        Returns:
            S3キープレフィックス
        """
        return f"qeel/{subdir}"

    def get_partition_dir(self, base_path: str, target_datetime: datetime) -> str:
        """年月パーティションキープレフィックスを返す（YYYY/MM/）

        S3はディレクトリの概念がないため、プレフィックスのみ返す。

        Args:
            base_path: ベースパス（キープレフィックス）
            target_datetime: パーティショニング対象の日時

        Returns:
            パーティションキープレフィックス
        """
        return f"{base_path}/{target_datetime.strftime('%Y')}/{target_datetime.strftime('%m')}"

    def save(self, path: str, data: dict[str, object] | pl.DataFrame, format: str) -> None:
        """S3に保存

        Args:
            path: S3キー
            data: 保存するデータ
            format: フォーマット（"json"または"parquet"）

        Raises:
            ValueError: サポートされていないフォーマット、
                       またはデータ型が不正な場合
        """
        if format == "json":
            body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
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

    def load(self, path: str, format: str) -> dict[str, object] | pl.DataFrame | None:
        """S3から読み込み

        Args:
            path: S3キー
            format: フォーマット（"json"または"parquet"）

        Returns:
            読み込んだデータ。存在しない場合はNone

        Raises:
            ValueError: サポートされていないフォーマット
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=path)
            body = response["Body"].read()

            if format == "json":
                return json.loads(body.decode("utf-8"))  # type: ignore[no-any-return]
            elif format == "parquet":
                buffer = BytesIO(body)
                return pl.read_parquet(buffer)
            else:
                raise ValueError(f"サポートされていないフォーマット: {format}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise

    def exists(self, path: str) -> bool:
        """S3オブジェクトの存在確認

        Args:
            path: S3キー

        Returns:
            オブジェクトが存在する場合True
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=path)
            return True
        except ClientError:
            return False

    def list_files(self, path: str, pattern: str | None = None) -> list[str]:
        """指定プレフィックス配下のオブジェクト一覧を取得

        Args:
            path: S3キープレフィックス
            pattern: ファイル名のフィルタパターン（fnmatch形式）

        Returns:
            マッチしたS3キーのリスト（ソート済み）
        """
        paginator = self.s3_client.get_paginator("list_objects_v2")
        files: list[str] = []

        for page in paginator.paginate(Bucket=self.bucket, Prefix=path):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if pattern:
                    filename = key.split("/")[-1]
                    if fnmatch.fnmatch(filename, pattern):
                        files.append(key)
                else:
                    files.append(key)

        return sorted(files)
