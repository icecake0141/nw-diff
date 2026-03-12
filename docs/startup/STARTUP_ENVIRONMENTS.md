# Environment-Specific Startup / 環境別起動方法

## Table of Contents
- [English](#english)
  - [Environment Matrix](#environment-matrix)
  - [Development Startup](#development-startup)
  - [Staging Startup](#staging-startup)
  - [Production Startup](#production-startup)
- [日本語](#日本語)
  - [環境マトリクス](#環境マトリクス)
  - [開発環境での起動](#開発環境での起動)
  - [ステージング環境での起動](#ステージング環境での起動)
  - [本番環境での起動](#本番環境での起動)

## English

### Environment Matrix
| Environment | Required Variables | Command |
|---|---|---|
| Development | `DEVICE_PASSWORD`, `NW_DIFF_ENV=development` | `./scripts/start-v2.sh` |
| Staging | `DEVICE_PASSWORD`, `NW_DIFF_ENV=staging`, `NW_DIFF_API_TOKEN` | `./scripts/start-v2.sh` |
| Production | `DEVICE_PASSWORD`, `NW_DIFF_ENV=production`, `NW_DIFF_API_TOKEN` | `./scripts/start-v2.sh` |

### Development Startup
```bash
export DEVICE_PASSWORD=your_device_password
export NW_DIFF_ENV=development
./scripts/start-v2.sh
```

### Staging Startup
```bash
export DEVICE_PASSWORD=your_device_password
export NW_DIFF_ENV=staging
export NW_DIFF_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
./scripts/start-v2.sh
```

### Production Startup
```bash
export DEVICE_PASSWORD=your_device_password
export NW_DIFF_ENV=production
export NW_DIFF_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
./scripts/start-v2.sh
```

The script prints required variables before launch and masks sensitive values.

## 日本語

### 環境マトリクス
| 環境 | 必須変数 | 起動コマンド |
|---|---|---|
| 開発 | `DEVICE_PASSWORD`, `NW_DIFF_ENV=development` | `./scripts/start-v2.sh` |
| ステージング | `DEVICE_PASSWORD`, `NW_DIFF_ENV=staging`, `NW_DIFF_API_TOKEN` | `./scripts/start-v2.sh` |
| 本番 | `DEVICE_PASSWORD`, `NW_DIFF_ENV=production`, `NW_DIFF_API_TOKEN` | `./scripts/start-v2.sh` |

### 開発環境での起動
```bash
export DEVICE_PASSWORD=your_device_password
export NW_DIFF_ENV=development
./scripts/start-v2.sh
```

### ステージング環境での起動
```bash
export DEVICE_PASSWORD=your_device_password
export NW_DIFF_ENV=staging
export NW_DIFF_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
./scripts/start-v2.sh
```

### 本番環境での起動
```bash
export DEVICE_PASSWORD=your_device_password
export NW_DIFF_ENV=production
export NW_DIFF_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
./scripts/start-v2.sh
```

起動スクリプトは実行前に必須変数を表示し、センシティブな値をマスクします。
