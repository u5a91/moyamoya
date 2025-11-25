# Dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.8.3

# 必要なツール
RUN apt-get update && apt-get install -y curl build-essential && rm -rf /var/lib/apt/lists/*

# Poetry をインストール
RUN pip install "poetry==$POETRY_VERSION"

WORKDIR /app

# 依存関係だけ先にコピー
COPY pyproject.toml poetry.lock* ./

# コンテナ内では venv を作らずグローバルに入れる設定
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# アプリ本体をコピー
COPY . .

# コンテナ起動時のコマンド
CMD ["poetry", "run", "python", "app.py"]
