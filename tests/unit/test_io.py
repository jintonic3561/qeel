"""IOレイヤーのテスト"""

import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import boto3
import polars as pl
import pytest
from moto import mock_aws

from qeel.config import GeneralConfig


class TestBaseIO:
    """BaseIO ABCのテスト"""

    def test_base_io_cannot_instantiate(self) -> None:
        """ABCは直接インスタンス化不可"""
        from qeel.io.base import BaseIO

        with pytest.raises(TypeError):
            BaseIO()  # type: ignore[abstract]

    def test_from_config_returns_local_io(self) -> None:
        """storage_type='local'でLocalIOを返す"""
        from qeel.io.base import BaseIO
        from qeel.io.local import LocalIO

        config = GeneralConfig(storage_type="local")
        io = BaseIO.from_config(config)

        assert isinstance(io, LocalIO)

    def test_from_config_returns_s3_io(self) -> None:
        """storage_type='s3'でS3IOを返す"""
        from qeel.io.base import BaseIO
        from qeel.io.s3 import S3IO

        config = GeneralConfig(
            storage_type="s3",
            s3_bucket="test-bucket",
            s3_region="ap-northeast-1",
        )
        io = BaseIO.from_config(config)

        assert isinstance(io, S3IO)

    def test_from_config_raises_on_unsupported_storage(self) -> None:
        """サポートされていないstorage_typeでValueError"""
        from qeel.io.base import BaseIO

        # GeneralConfigのバリデーションを回避して直接テスト
        config = MagicMock()
        config.storage_type = "gcs"  # サポートされていないタイプ

        with pytest.raises(ValueError, match="サポートされていないストレージタイプ"):
            BaseIO.from_config(config)

    def test_from_config_raises_s3_missing_bucket(self) -> None:
        """s3でbucket未設定時にValueError"""
        from qeel.io.base import BaseIO

        config = MagicMock()
        config.storage_type = "s3"
        config.s3_bucket = None
        config.s3_region = "ap-northeast-1"

        with pytest.raises(ValueError, match="s3_bucketとs3_regionは必須"):
            BaseIO.from_config(config)

    def test_from_config_raises_s3_missing_region(self) -> None:
        """s3でregion未設定時にValueError"""
        from qeel.io.base import BaseIO

        config = MagicMock()
        config.storage_type = "s3"
        config.s3_bucket = "test-bucket"
        config.s3_region = None

        with pytest.raises(ValueError, match="s3_bucketとs3_regionは必須"):
            BaseIO.from_config(config)


class TestLocalIO:
    """LocalIOのテスト"""

    def test_local_io_get_base_path_returns_workspace_subdir(
        self, tmp_path: Path
    ) -> None:
        """ワークスペース配下のパスを返す"""
        from qeel.io.local import LocalIO

        with patch("qeel.io.local.get_workspace", return_value=tmp_path):
            io = LocalIO()
            base_path = io.get_base_path("outputs")

        assert base_path == str(tmp_path / "outputs")

    def test_local_io_get_partition_dir_creates_directory(
        self, tmp_path: Path
    ) -> None:
        """年月パーティションディレクトリを作成して返す"""
        from qeel.io.local import LocalIO

        with patch("qeel.io.local.get_workspace", return_value=tmp_path):
            io = LocalIO()
            base_path = str(tmp_path / "outputs")
            target_datetime = datetime(2025, 1, 15)

            partition_dir = io.get_partition_dir(base_path, target_datetime)

        expected_dir = tmp_path / "outputs" / "2025" / "01"
        assert partition_dir == str(expected_dir)
        assert expected_dir.exists()

    def test_local_io_save_json(self, tmp_path: Path) -> None:
        """dict形式でJSONファイルに保存"""
        from qeel.io.local import LocalIO

        with patch("qeel.io.local.get_workspace", return_value=tmp_path):
            io = LocalIO()
            data = {"key": "value", "number": 42}
            path = str(tmp_path / "test.json")

            io.save(path, data, format="json")

        assert Path(path).exists()
        import json

        with open(path) as f:
            loaded = json.load(f)
        assert loaded == data

    def test_local_io_save_parquet(self, tmp_path: Path) -> None:
        """DataFrame形式でParquetファイルに保存"""
        from qeel.io.local import LocalIO

        with patch("qeel.io.local.get_workspace", return_value=tmp_path):
            io = LocalIO()
            df = pl.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
            path = str(tmp_path / "test.parquet")

            io.save(path, df, format="parquet")

        assert Path(path).exists()
        loaded = pl.read_parquet(path)
        assert loaded.shape == (3, 2)

    def test_local_io_save_raises_unsupported_format(self, tmp_path: Path) -> None:
        """サポートされていないフォーマットでValueError"""
        from qeel.io.local import LocalIO

        with patch("qeel.io.local.get_workspace", return_value=tmp_path):
            io = LocalIO()
            path = str(tmp_path / "test.csv")

            with pytest.raises(ValueError, match="サポートされていないフォーマット"):
                io.save(path, {"key": "value"}, format="csv")

    def test_local_io_save_parquet_raises_invalid_data(self, tmp_path: Path) -> None:
        """parquetでdict指定時にValueError"""
        from qeel.io.local import LocalIO

        with patch("qeel.io.local.get_workspace", return_value=tmp_path):
            io = LocalIO()
            path = str(tmp_path / "test.parquet")

            with pytest.raises(ValueError, match="pl.DataFrameが必要"):
                io.save(path, {"key": "value"}, format="parquet")

    def test_local_io_load_json(self, tmp_path: Path) -> None:
        """JSONファイルからdictを読み込み"""
        from qeel.io.local import LocalIO

        import json

        data = {"key": "value", "number": 42}
        path = tmp_path / "test.json"
        with open(path, "w") as f:
            json.dump(data, f)

        with patch("qeel.io.local.get_workspace", return_value=tmp_path):
            io = LocalIO()
            loaded = io.load(str(path), format="json")

        assert loaded == data

    def test_local_io_load_parquet(self, tmp_path: Path) -> None:
        """ParquetファイルからDataFrameを読み込み"""
        from qeel.io.local import LocalIO

        df = pl.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
        path = tmp_path / "test.parquet"
        df.write_parquet(path)

        with patch("qeel.io.local.get_workspace", return_value=tmp_path):
            io = LocalIO()
            loaded = io.load(str(path), format="parquet")

        assert isinstance(loaded, pl.DataFrame)
        assert loaded.shape == (3, 2)

    def test_local_io_load_returns_none_when_not_exists(
        self, tmp_path: Path
    ) -> None:
        """ファイルが存在しない場合None"""
        from qeel.io.local import LocalIO

        with patch("qeel.io.local.get_workspace", return_value=tmp_path):
            io = LocalIO()
            loaded = io.load(str(tmp_path / "nonexistent.json"), format="json")

        assert loaded is None

    def test_local_io_load_raises_unsupported_format(self, tmp_path: Path) -> None:
        """サポートされていないフォーマットでValueError"""
        from qeel.io.local import LocalIO

        path = tmp_path / "test.txt"
        path.touch()

        with patch("qeel.io.local.get_workspace", return_value=tmp_path):
            io = LocalIO()

            with pytest.raises(ValueError, match="サポートされていないフォーマット"):
                io.load(str(path), format="csv")

    def test_local_io_exists_returns_true(self, tmp_path: Path) -> None:
        """ファイルが存在する場合True"""
        from qeel.io.local import LocalIO

        path = tmp_path / "test.txt"
        path.touch()

        with patch("qeel.io.local.get_workspace", return_value=tmp_path):
            io = LocalIO()
            assert io.exists(str(path)) is True

    def test_local_io_exists_returns_false(self, tmp_path: Path) -> None:
        """ファイルが存在しない場合False"""
        from qeel.io.local import LocalIO

        with patch("qeel.io.local.get_workspace", return_value=tmp_path):
            io = LocalIO()
            assert io.exists(str(tmp_path / "nonexistent.txt")) is False

    def test_local_io_list_files_returns_all(self, tmp_path: Path) -> None:
        """指定パス配下の全ファイルを返す"""
        from qeel.io.local import LocalIO

        # テストファイルを作成
        subdir = tmp_path / "data"
        subdir.mkdir()
        (subdir / "file1.parquet").touch()
        (subdir / "file2.parquet").touch()
        (subdir / "file3.json").touch()

        with patch("qeel.io.local.get_workspace", return_value=tmp_path):
            io = LocalIO()
            files = io.list_files(str(subdir))

        assert len(files) == 3

    def test_local_io_list_files_with_pattern(self, tmp_path: Path) -> None:
        """パターン指定でフィルタリング"""
        from qeel.io.local import LocalIO

        subdir = tmp_path / "data"
        subdir.mkdir()
        (subdir / "signals_2025-01-01.parquet").touch()
        (subdir / "signals_2025-01-02.parquet").touch()
        (subdir / "portfolio_2025-01-01.parquet").touch()

        with patch("qeel.io.local.get_workspace", return_value=tmp_path):
            io = LocalIO()
            files = io.list_files(str(subdir), pattern="signals_*.parquet")

        assert len(files) == 2
        assert all("signals_" in f for f in files)

    def test_local_io_list_files_returns_empty_when_not_exists(
        self, tmp_path: Path
    ) -> None:
        """存在しないパスで空リスト"""
        from qeel.io.local import LocalIO

        with patch("qeel.io.local.get_workspace", return_value=tmp_path):
            io = LocalIO()
            files = io.list_files(str(tmp_path / "nonexistent"))

        assert files == []


class TestS3IO:
    """S3IOのテスト（motoでAWS APIをモック）"""

    @pytest.fixture
    def s3_bucket(self) -> str:
        """テスト用バケット名"""
        return "test-bucket"

    @pytest.fixture
    def s3_region(self) -> str:
        """テスト用リージョン"""
        return "ap-northeast-1"

    @pytest.fixture
    def mock_s3(self, s3_bucket: str, s3_region: str):
        """motoでS3をモック"""
        with mock_aws():
            # バケットを作成
            s3_client = boto3.client("s3", region_name=s3_region)
            s3_client.create_bucket(
                Bucket=s3_bucket,
                CreateBucketConfiguration={"LocationConstraint": s3_region},
            )
            yield s3_client

    def test_s3_io_get_base_path_returns_prefix(
        self, mock_s3, s3_bucket: str, s3_region: str
    ) -> None:
        """S3キープレフィックスを返す"""
        from qeel.io.s3 import S3IO

        io = S3IO(bucket=s3_bucket, region=s3_region)
        base_path = io.get_base_path("outputs")

        assert base_path == "qeel/outputs"

    def test_s3_io_get_partition_dir_returns_prefix(
        self, mock_s3, s3_bucket: str, s3_region: str
    ) -> None:
        """年月パーティションプレフィックスを返す"""
        from qeel.io.s3 import S3IO

        io = S3IO(bucket=s3_bucket, region=s3_region)
        base_path = "qeel/outputs"
        target_datetime = datetime(2025, 1, 15)

        partition_dir = io.get_partition_dir(base_path, target_datetime)

        assert partition_dir == "qeel/outputs/2025/01"

    def test_s3_io_save_json(
        self, mock_s3, s3_bucket: str, s3_region: str
    ) -> None:
        """dict形式でS3にJSON保存"""
        from qeel.io.s3 import S3IO

        io = S3IO(bucket=s3_bucket, region=s3_region)
        data = {"key": "value", "number": 42}
        path = "test/data.json"

        io.save(path, data, format="json")

        # 直接S3から読み込んで確認
        import json

        response = mock_s3.get_object(Bucket=s3_bucket, Key=path)
        loaded = json.loads(response["Body"].read().decode("utf-8"))
        assert loaded == data

    def test_s3_io_save_parquet(
        self, mock_s3, s3_bucket: str, s3_region: str
    ) -> None:
        """DataFrame形式でS3にParquet保存"""
        from qeel.io.s3 import S3IO

        io = S3IO(bucket=s3_bucket, region=s3_region)
        df = pl.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
        path = "test/data.parquet"

        io.save(path, df, format="parquet")

        # 直接S3から読み込んで確認
        from io import BytesIO

        response = mock_s3.get_object(Bucket=s3_bucket, Key=path)
        buffer = BytesIO(response["Body"].read())
        loaded = pl.read_parquet(buffer)
        assert loaded.shape == (3, 2)

    def test_s3_io_save_raises_unsupported_format(
        self, mock_s3, s3_bucket: str, s3_region: str
    ) -> None:
        """サポートされていないフォーマットでValueError"""
        from qeel.io.s3 import S3IO

        io = S3IO(bucket=s3_bucket, region=s3_region)

        with pytest.raises(ValueError, match="サポートされていないフォーマット"):
            io.save("test.csv", {"key": "value"}, format="csv")

    def test_s3_io_load_json(
        self, mock_s3, s3_bucket: str, s3_region: str
    ) -> None:
        """S3からJSONを読み込み"""
        from qeel.io.s3 import S3IO

        import json

        # テストデータをS3に保存
        data = {"key": "value", "number": 42}
        path = "test/data.json"
        mock_s3.put_object(
            Bucket=s3_bucket,
            Key=path,
            Body=json.dumps(data).encode("utf-8"),
        )

        io = S3IO(bucket=s3_bucket, region=s3_region)
        loaded = io.load(path, format="json")

        assert loaded == data

    def test_s3_io_load_parquet(
        self, mock_s3, s3_bucket: str, s3_region: str
    ) -> None:
        """S3からParquetを読み込み"""
        from io import BytesIO

        from qeel.io.s3 import S3IO

        # テストデータをS3に保存
        df = pl.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
        path = "test/data.parquet"
        buffer = BytesIO()
        df.write_parquet(buffer)
        mock_s3.put_object(Bucket=s3_bucket, Key=path, Body=buffer.getvalue())

        io = S3IO(bucket=s3_bucket, region=s3_region)
        loaded = io.load(path, format="parquet")

        assert isinstance(loaded, pl.DataFrame)
        assert loaded.shape == (3, 2)

    def test_s3_io_load_returns_none_when_not_exists(
        self, mock_s3, s3_bucket: str, s3_region: str
    ) -> None:
        """キーが存在しない場合None"""
        from qeel.io.s3 import S3IO

        io = S3IO(bucket=s3_bucket, region=s3_region)
        loaded = io.load("nonexistent/path.json", format="json")

        assert loaded is None

    def test_s3_io_exists_returns_true(
        self, mock_s3, s3_bucket: str, s3_region: str
    ) -> None:
        """オブジェクトが存在する場合True"""
        from qeel.io.s3 import S3IO

        path = "test/data.json"
        mock_s3.put_object(Bucket=s3_bucket, Key=path, Body=b"test")

        io = S3IO(bucket=s3_bucket, region=s3_region)
        assert io.exists(path) is True

    def test_s3_io_exists_returns_false(
        self, mock_s3, s3_bucket: str, s3_region: str
    ) -> None:
        """オブジェクトが存在しない場合False"""
        from qeel.io.s3 import S3IO

        io = S3IO(bucket=s3_bucket, region=s3_region)
        assert io.exists("nonexistent/path.json") is False

    def test_s3_io_list_files_returns_all(
        self, mock_s3, s3_bucket: str, s3_region: str
    ) -> None:
        """指定プレフィックス配下の全オブジェクトを返す"""
        from qeel.io.s3 import S3IO

        # テストオブジェクトを作成
        prefix = "data"
        mock_s3.put_object(Bucket=s3_bucket, Key=f"{prefix}/file1.parquet", Body=b"1")
        mock_s3.put_object(Bucket=s3_bucket, Key=f"{prefix}/file2.parquet", Body=b"2")
        mock_s3.put_object(Bucket=s3_bucket, Key=f"{prefix}/file3.json", Body=b"3")

        io = S3IO(bucket=s3_bucket, region=s3_region)
        files = io.list_files(prefix)

        assert len(files) == 3

    def test_s3_io_list_files_with_pattern(
        self, mock_s3, s3_bucket: str, s3_region: str
    ) -> None:
        """パターン指定でフィルタリング"""
        from qeel.io.s3 import S3IO

        prefix = "data"
        mock_s3.put_object(
            Bucket=s3_bucket, Key=f"{prefix}/signals_2025-01-01.parquet", Body=b"1"
        )
        mock_s3.put_object(
            Bucket=s3_bucket, Key=f"{prefix}/signals_2025-01-02.parquet", Body=b"2"
        )
        mock_s3.put_object(
            Bucket=s3_bucket, Key=f"{prefix}/portfolio_2025-01-01.parquet", Body=b"3"
        )

        io = S3IO(bucket=s3_bucket, region=s3_region)
        files = io.list_files(prefix, pattern="signals_*.parquet")

        assert len(files) == 2
        assert all("signals_" in f for f in files)


class TestInMemoryIO:
    """InMemoryIOのテスト"""

    def test_in_memory_io_save_and_load_json(self) -> None:
        """dict形式で保存・読み込み"""
        from qeel.io.in_memory import InMemoryIO

        io = InMemoryIO()
        data = {"key": "value", "number": 42}
        path = "test/data.json"

        io.save(path, data, format="json")
        loaded = io.load(path, format="json")

        assert loaded == data

    def test_in_memory_io_save_and_load_dataframe(self) -> None:
        """DataFrame形式で保存・読み込み"""
        from qeel.io.in_memory import InMemoryIO

        io = InMemoryIO()
        df = pl.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
        path = "test/data.parquet"

        io.save(path, df, format="parquet")
        loaded = io.load(path, format="parquet")

        assert isinstance(loaded, pl.DataFrame)
        assert loaded.shape == (3, 2)

    def test_in_memory_io_exists(self) -> None:
        """存在確認"""
        from qeel.io.in_memory import InMemoryIO

        io = InMemoryIO()
        path = "test/data.json"

        assert io.exists(path) is False

        io.save(path, {"key": "value"}, format="json")

        assert io.exists(path) is True

    def test_in_memory_io_list_files(self) -> None:
        """ファイル一覧取得"""
        from qeel.io.in_memory import InMemoryIO

        io = InMemoryIO()

        io.save("data/signals_2025-01-01.parquet", pl.DataFrame({"a": [1]}), format="parquet")
        io.save("data/signals_2025-01-02.parquet", pl.DataFrame({"a": [2]}), format="parquet")
        io.save("data/portfolio_2025-01-01.parquet", pl.DataFrame({"a": [3]}), format="parquet")

        # 全ファイル
        all_files = io.list_files("data")
        assert len(all_files) == 3

        # パターン指定
        signal_files = io.list_files("data", pattern="signals_*.parquet")
        assert len(signal_files) == 2

    def test_in_memory_io_get_base_path(self) -> None:
        """ベースパス取得"""
        from qeel.io.in_memory import InMemoryIO

        io = InMemoryIO()
        base_path = io.get_base_path("outputs")

        assert base_path == "memory://outputs"

    def test_in_memory_io_get_partition_dir(self) -> None:
        """パーティションディレクトリ取得"""
        from qeel.io.in_memory import InMemoryIO

        io = InMemoryIO()
        base_path = "memory://outputs"
        target_datetime = datetime(2025, 1, 15)

        partition_dir = io.get_partition_dir(base_path, target_datetime)

        assert partition_dir == "memory://outputs/2025/01"
