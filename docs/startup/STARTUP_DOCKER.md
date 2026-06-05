# Docker and Podman Startup / Docker・Podmanでの起動方法

## Table of Contents
- [English](#english)
  - [Docker Prerequisites](#docker-prerequisites)
  - [Docker Quick Start](#docker-quick-start)
  - [Docker Access and Logs](#docker-access-and-logs)
  - [Docker Stop](#docker-stop)
  - [Podman Prerequisites](#podman-prerequisites)
  - [Podman Quick Start](#podman-quick-start)
  - [Podman Access and Logs](#podman-access-and-logs)
  - [Podman Stop](#podman-stop)
  - [Compatibility Notes (Best-effort)](#compatibility-notes-best-effort)
- [日本語](#日本語)
  - [Docker 前提条件](#docker-前提条件)
  - [Docker クイックスタート](#docker-クイックスタート)
  - [Docker アクセスとログ確認](#docker-アクセスとログ確認)
  - [Docker 停止](#docker-停止)
  - [Podman 前提条件](#podman-前提条件)
  - [Podman クイックスタート](#podman-クイックスタート)
  - [Podman アクセスとログ確認](#podman-アクセスとログ確認)
  - [Podman 停止](#podman-停止)
  - [互換性に関する注意（Best-effort）](#互換性に関する注意best-effort)

## English

### Docker Prerequisites
- Docker
- Docker Compose (`docker compose`)

### Docker Quick Start
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

### Docker Access and Logs
- Access: [https://localhost/](https://localhost/)
- Logs:
```bash
docker compose logs -f
```

### Docker Stop
```bash
docker compose down
```

### Podman Prerequisites
- Podman
- Podman Compose (`podman compose`)

### Podman Quick Start
```bash
cp .env.example .env
# edit .env and set at least DEVICE_PASSWORD and NW_DIFF_API_TOKEN

cp hosts.csv.sample hosts.csv

# generate self-signed cert and Basic Auth file (recommended)
export NW_DIFF_BASIC_USER=admin
export NW_DIFF_BASIC_PASSWORD=change_me_now
./docker/nginx/init-certs-and-htpasswd.sh

podman compose up -d
```

### Podman Access and Logs
- Access: [https://localhost/](https://localhost/)
- Logs:
```bash
podman compose logs -f
```

### Podman Stop
```bash
podman compose down
```

### Compatibility Notes (Best-effort)
- Podman support is best-effort.
- Compose behavior may differ by environment and Podman setup.
- Rootless mode, SELinux policy, and port-binding behavior may require host-side adjustments.
- If startup fails, first try reproducing with Docker to isolate runtime-specific issues.

## 日本語

### Docker 前提条件
- Docker
- Docker Compose（`docker compose`）

### Docker クイックスタート
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

### Docker アクセスとログ確認
- アクセス先: [https://localhost/](https://localhost/)
- ログ確認:
```bash
docker compose logs -f
```

### Docker 停止
```bash
docker compose down
```

### Podman 前提条件
- Podman
- Podman Compose（`podman compose`）

### Podman クイックスタート
```bash
cp .env.example .env
# .env を編集して最低でも DEVICE_PASSWORD と NW_DIFF_API_TOKEN を設定

cp hosts.csv.sample hosts.csv

# 自己署名証明書と Basic 認証ファイルを作成（推奨）
export NW_DIFF_BASIC_USER=admin
export NW_DIFF_BASIC_PASSWORD=change_me_now
./docker/nginx/init-certs-and-htpasswd.sh

podman compose up -d
```

### Podman アクセスとログ確認
- アクセス先: [https://localhost/](https://localhost/)
- ログ確認:
```bash
podman compose logs -f
```

### Podman 停止
```bash
podman compose down
```

### 互換性に関する注意（Best-effort）
- Podman 対応は best-effort です。
- Compose の挙動は環境や Podman の設定差により異なる場合があります。
- rootless モード、SELinux ポリシー、ポート割り当てによりホスト側調整が必要になる場合があります。
- 起動に失敗する場合は、まず Docker で再現確認してランタイム依存の問題か切り分けてください。
