"""ワークスペース管理ユーティリティ

環境変数QEEL_WORKSPACEでワークスペースディレクトリを指定可能。
未設定の場合はカレントディレクトリを返す。
"""

import os
from pathlib import Path


def get_workspace() -> Path:
    """ワークスペースディレクトリを取得する

    環境変数QEEL_WORKSPACEが設定されている場合はそのパスを返し、
    未設定の場合はカレントディレクトリを返す。

    Returns:
        ワークスペースディレクトリのPathオブジェクト

    Raises:
        ValueError: 指定されたパスが存在しないディレクトリの場合

    Example:
        # 環境変数で指定
        $ export QEEL_WORKSPACE=/path/to/my_backtest
        >>> get_workspace()
        PosixPath('/path/to/my_backtest')

        # 環境変数未設定(カレントディレクトリを使用)
        >>> get_workspace()
        PosixPath('/current/working/directory')
    """
    workspace_env = os.environ.get("QEEL_WORKSPACE")

    if workspace_env is not None:
        workspace = Path(workspace_env)
        if not workspace.is_dir():
            raise ValueError(f"QEEL_WORKSPACEで指定されたパスが存在しないか、ディレクトリではありません: {workspace}")
        return workspace

    return Path.cwd()
