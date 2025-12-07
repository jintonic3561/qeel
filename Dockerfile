# 公式Pythonベースイメージを使用（Python 3.12 on Debian）
FROM python:3.12-slim

# ワークディレクトリを設定
WORKDIR /app

# 必要な基本パッケージをインストール
RUN apt-get update && \
    apt-get install -y \
    tar \
    gzip \
    git \
    curl \
    sudo \
    gnupg \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# GitHub CLI (gh) のインストール
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && \
    chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    | tee /etc/apt/sources.list.d/github-cli.list > /dev/null && \
    apt-get update && \
    apt-get install -y gh && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# uvパッケージマネージャのインストール
# 公式推奨の方法: ghcr.io/astral-sh/uv:latestからバイナリをコピー
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# プロジェクトメタデータと依存関係定義ファイルをコピー
COPY pyproject.toml ./

# アプリケーションコードをコピー
COPY src/ ./src/

# Python依存関係のインストール
# --frozen: uv.lockが存在する場合はそれを使用、変更を許可しない
# --no-dev: 本番用依存関係のみインストール（dev依存関係は除外）
RUN uv sync --frozen --no-dev || uv sync --no-dev

# 開発ツールのインストール

# Node.js環境のセットアップ
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Claude Code CLIとSpeckit CLIのインストール
# DevContainer環境で使用するツールをインストール

# エージェントをnpmでグローバルインストール
RUN npm install -g @anthropic-ai/claude-code
RUN npm install -g @google/gemini-cli

# Speckit CLIをuvでインストール（公式推奨の方法）
# uv tool installでグローバルCLIツールとしてインストール
RUN uv tool install specify-cli --from git+https://github.com/github/spec-kit.git

# uv tool でインストールしたCLIツールをPATHに追加
ENV PATH="/root/.local/bin:${PATH}"

# コンテナ起動時にbashを起動
CMD ["/bin/bash"]
