#!/usr/bin/env python3
"""ユーザープロンプトをブランチ別のraw.mdにログ記録するhook"""

import json
import os
import subprocess
import sys
from pathlib import Path


def get_model_from_transcript(transcript_path: str) -> str:
    """transcript JSONLからモデル名を抽出"""
    try:
        path = Path(transcript_path)
        if not path.exists():
            return "unknown"

        # JSONLファイルを逆順で読み、最新のモデル情報を探す
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()

        for line in reversed(lines):
            try:
                entry = json.loads(line.strip())
                # message.model からモデル情報を探す
                if "message" in entry and isinstance(entry["message"], dict):
                    model = entry["message"].get("model", "")
                    if model:
                        # モデル名を短縮形に変換（例: claude-opus-4-5-20251101 -> opus）
                        if "opus" in model:
                            return "opus"
                        elif "sonnet" in model:
                            return "sonnet"
                        elif "haiku" in model:
                            return "haiku"
                        return model
            except json.JSONDecodeError:
                continue

        return "unknown"
    except Exception:
        return "unknown"


def get_session_name_from_path(transcript_path: str) -> str:
    """transcript pathからセッション名（ファイル名）を抽出"""
    try:
        return Path(transcript_path).stem
    except Exception:
        return "unknown"


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

    # メタ情報を抽出
    session_id = input_data.get("session_id", "unknown")
    transcript_path = input_data.get("transcript_path", "")

    # モデル名とセッション名を取得
    model = get_model_from_transcript(transcript_path)
    session_name = get_session_name_from_path(transcript_path)

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

    # メタ情報フッターを作成
    meta_footer = f"[model: {model}, session: {session_name[:8]}]"

    # ファイルに追記
    with open(log_file, "a", encoding="utf-8") as f:
        # 既存ファイルには区切り線を先に追加
        if log_file.stat().st_size > 0:
            f.write("\n---\n\n")
        f.write(prompt)
        f.write(f"\n\n{meta_footer}\n")


if __name__ == "__main__":
    main()
