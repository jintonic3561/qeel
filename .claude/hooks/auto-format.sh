#!/bin/bash

# プロジェクトディレクトリを取得
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"

# 変更されたPythonファイルを取得
MODIFIED_PYTHON_FILES=$(
  cd "$PROJECT_DIR" && \
  git diff --name-only --diff-filter=ACMTU 2>/dev/null | \
  grep '\.py$' | \
  grep -v __pycache__ || true
)

if [ -z "$MODIFIED_PYTHON_FILES" ]; then
  echo "フォーマット対象のPythonファイルなし"
  exit 0
fi

echo "変更されたPythonファイルをフォーマット:"
echo "$MODIFIED_PYTHON_FILES"

# ruff format と ruff check --fix を実行
cd "$PROJECT_DIR"
echo "$MODIFIED_PYTHON_FILES" | xargs -r uv run ruff format
echo "$MODIFIED_PYTHON_FILES" | xargs -r uv run ruff check --fix

echo "✅ フォーマット完了"
exit 0
