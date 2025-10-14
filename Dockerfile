# Python 3.11をベースイメージとして使用
FROM python:3.11-slim

# 作業ディレクトリを設定
WORKDIR /app

# システムパッケージの更新と必要なツールのインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Pythonの依存関係をコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのソースコードをコピー
COPY *.py .
COPY .env.example .env.example

# ベクトルDB、認証情報、ログ用のディレクトリを作成
RUN mkdir -p /app/chroma_db_openai /app/credentials /app/logs

# 環境変数を設定（デフォルト値）
ENV PYTHONUNBUFFERED=1

# ヘルスチェック用のスクリプト
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import os; exit(0 if os.path.exists('/tmp/bot_ready') else 1)"

# Slackボットを起動
CMD ["python", "-u", "slack_bot_hybrid.py"]

