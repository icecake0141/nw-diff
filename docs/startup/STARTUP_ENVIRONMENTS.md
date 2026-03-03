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
| Development | `DEVICE_PASSWORD`, `NW_DIFF_ENV=development` | `uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src` |
| Staging | `DEVICE_PASSWORD`, `NW_DIFF_ENV=staging`, `NW_DIFF_API_TOKEN` | `uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src` |
| Production | `DEVICE_PASSWORD`, `NW_DIFF_ENV=production`, `NW_DIFF_API_TOKEN` | `uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src` |

### Development Startup
```bash
export DEVICE_PASSWORD=your_device_password
export NW_DIFF_ENV=development
uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src
```

### Staging Startup
```bash
export DEVICE_PASSWORD=your_device_password
export NW_DIFF_ENV=staging
export NW_DIFF_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src
```

### Production Startup
```bash
export DEVICE_PASSWORD=your_device_password
export NW_DIFF_ENV=production
export NW_DIFF_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src
```

## 日本語

### 環境マトリクス
| 環境 | 必須変数 | 起動コマンド |
|---|---|---|
| 開発 | `DEVICE_PASSWORD`, `NW_DIFF_ENV=development` | `uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src` |
| ステージング | `DEVICE_PASSWORD`, `NW_DIFF_ENV=staging`, `NW_DIFF_API_TOKEN` | `uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src` |
| 本番 | `DEVICE_PASSWORD`, `NW_DIFF_ENV=production`, `NW_DIFF_API_TOKEN` | `uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src` |

### 開発環境での起動
```bash
export DEVICE_PASSWORD=your_device_password
export NW_DIFF_ENV=development
uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src
```

### ステージング環境での起動
```bash
export DEVICE_PASSWORD=your_device_password
export NW_DIFF_ENV=staging
export NW_DIFF_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src
```

### 本番環境での起動
```bash
export DEVICE_PASSWORD=your_device_password
export NW_DIFF_ENV=production
export NW_DIFF_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src
```
