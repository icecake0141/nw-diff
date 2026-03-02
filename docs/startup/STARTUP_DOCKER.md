# Docker Startup / Dockerでの起動方法

## Table of Contents
- [English](#english)
  - [Prerequisites](#prerequisites)
  - [Quick Start](#quick-start)
  - [Access and Logs](#access-and-logs)
  - [Stop](#stop)
- [日本語](#日本語)
  - [前提条件](#前提条件)
  - [クイックスタート](#クイックスタート)
  - [アクセスとログ確認](#アクセスとログ確認)
  - [停止](#停止)

## English

### Prerequisites
- Docker
- Docker Compose (`docker compose`)

### Quick Start
```bash
cp .env.example .env
# edit .env and set at least DEVICE_PASSWORD and NW_DIFF_API_TOKEN

cp hosts.csv.sample hosts.csv

# generate self-signed cert and Basic Auth file (recommended)
export NW_DIFF_BASIC_USER=admin
export NW_DIFF_BASIC_PASSWORD=change_me_now
./docker/nginx/init-certs-and-htpasswd.sh

docker compose up -d
```

### Access and Logs
- Access: [https://localhost/](https://localhost/)
- Logs:
```bash
docker compose logs -f
```

### Stop
```bash
docker compose down
```

## 日本語

### 前提条件
- Docker
- Docker Compose（`docker compose`）

### クイックスタート
```bash
cp .env.example .env
# .env を編集して最低でも DEVICE_PASSWORD と NW_DIFF_API_TOKEN を設定

cp hosts.csv.sample hosts.csv

# 自己署名証明書と Basic 認証ファイルを作成（推奨）
export NW_DIFF_BASIC_USER=admin
export NW_DIFF_BASIC_PASSWORD=change_me_now
./docker/nginx/init-certs-and-htpasswd.sh

docker compose up -d
```

### アクセスとログ確認
- アクセス先: [https://localhost/](https://localhost/)
- ログ確認:
```bash
docker compose logs -f
```

### 停止
```bash
docker compose down
```
