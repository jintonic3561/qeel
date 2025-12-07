#!/usr/bin/env python3
"""ユーザープロンプトをブランチ別のraw.mdにログ記録するhook"""

import json
import subprocess
import sys
from pathlib import Path


def main():
    # JSON入力を読み込む
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    # プロンプトを抽出
    prompt = input_data.get("prompt", "")
    if not prompt:
        sys.exit(0)

    # 現在のブランチ名を取得
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()
    except subprocess.CalledProcessError:
        branch = "unknown"

    # ログディレクトリとファイルパス
    log_dir = Path("./docs/prompt_logs") / branch
    log_file = log_dir / "raw.md"

    # ディレクトリがなければ作成
    log_dir.mkdir(parents=True, exist_ok=True)

    # ファイルに追記
    with open(log_file, "a", encoding="utf-8") as f:
        # 既存ファイルには区切り線を先に追加
        if log_file.stat().st_size > 0:
            f.write("\n---\n\n")
        f.write(prompt)
        f.write("\n")


if __name__ == "__main__":
    main()
