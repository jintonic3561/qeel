# Makefileターゲット定義

# 変数定義
IMAGE_NAME := qeel:latest
CONTAINER_NAME := qeel-dev
WORKSPACE_DIR := $(shell pwd)

.PHONY: build
build:
	# Dockerイメージをビルド
	# -t: イメージ名とタグを指定（qeel:latest）
	# .: ビルドコンテキストとしてカレントディレクトリを使用
	docker build -t $(IMAGE_NAME) .

.PHONY: run
run:
	# Dockerコンテナを起動
	# --name: コンテナ名を指定
	# --rm: コンテナ終了時に自動削除
	# -it: インタラクティブモード + 疑似TTY
	# --env-file: .envファイルから環境変数を読み込む
	# -v: カレントディレクトリを/appにマウント（devcontainerと同じ設定）
	# -w: 作業ディレクトリを/appに設定
	docker run --name $(CONTAINER_NAME) --rm -it \
		--env-file=.env \
		-v $(WORKSPACE_DIR):/app:cached \
		-w /app \
		$(IMAGE_NAME)

.PHONY: bash
bash:
	# 既存のコンテナが起動中ならそこでbashを起動、なければ新しくコンテナを起動
	@if docker ps -q -f name=$(CONTAINER_NAME) | grep -q .; then \
		echo "既存のコンテナでbashを起動..."; \
		docker exec -it $(CONTAINER_NAME) /bin/bash; \
	else \
		echo "新しいコンテナを起動してbashを実行..."; \
		$(MAKE) run; \
	fi

.PHONY: rm
rm:
	# Dockerコンテナを停止して削除
	@echo "コンテナを停止・削除..."
	@docker stop $(CONTAINER_NAME) 2>/dev/null || true
	@docker rm $(CONTAINER_NAME) 2>/dev/null || true
	@echo "完了"

.PHONY: clean
clean:
	# Dockerイメージも削除
	@$(MAKE) rm
	@echo "イメージを削除..."
	@docker rmi $(IMAGE_NAME) 2>/dev/null || true
	@echo "完了"

.PHONY: help
help:
	# 利用可能なコマンド一覧を表示
	@echo "利用可能なコマンド:"
	@echo "  make build  - Dockerイメージをビルド"
	@echo "  make run    - Dockerコンテナを起動（devcontainer環境と同等）"
	@echo "  make bash   - コンテナ内でbashを起動"
	@echo "  make rm     - Dockerコンテナを停止・削除"
	@echo "  make clean  - Dockerコンテナとイメージを削除"
	@echo "  make help   - このヘルプメッセージを表示"
