# Startup Troubleshooting / 起動トラブルシューティング

## Table of Contents
- [English](#english)
  - [Error: `NW_DIFF_ENV` not set and auth behavior is unexpected](#error-nw_diff_env-not-set-and-auth-behavior-is-unexpected)
  - [Error: `NW_DIFF_API_TOKEN` missing in non-development](#error-nw_diff_api_token-missing-in-non-development)
  - [Error: `DEVICE_PASSWORD` is required](#error-device_password-is-required)
  - [Error: `hosts.csv` not found](#error-hostscsv-not-found)
  - [Error: Browser cannot connect](#error-browser-cannot-connect)
- [日本語](#日本語)
  - [エラー: `NW_DIFF_ENV` 未設定で認証挙動が想定と違う](#エラー-nw_diff_env-未設定で認証挙動が想定と違う)
  - [エラー: 非開発環境で `NW_DIFF_API_TOKEN` が未設定](#エラー-非開発環境で-nw_diff_api_token-が未設定)
  - [エラー: `DEVICE_PASSWORD` is required](#エラー-device_password-is-required)
  - [エラー: `hosts.csv` が見つからない](#エラー-hostscsv-が見つからない)
  - [エラー: ブラウザから接続できない](#エラー-ブラウザから接続できない)

## English

### Error: `NW_DIFF_ENV` not set and auth behavior is unexpected
**Symptom**
- You expected local/development behavior, but protected endpoints return 503.

**Cause**
- `NW_DIFF_ENV` is not set to a development-like value (`development`, `dev`, `local`, `test`).

**Fix**
```bash
export NW_DIFF_ENV=development
```

### Error: `NW_DIFF_API_TOKEN` missing in non-development
**Symptom**
- API response: `Server authentication is not configured`.

**Cause**
- In non-development environments, missing `NW_DIFF_API_TOKEN` blocks protected endpoints.

**Fix**
```bash
export NW_DIFF_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

### Error: `DEVICE_PASSWORD` is required
**Symptom**
- Startup fails with `DEVICE_PASSWORD is required`.

**Fix**
```bash
export DEVICE_PASSWORD=your_device_password
```

### Error: `hosts.csv` not found
**Symptom**
- Host list/capture fails because inventory file is missing.

**Fix**
```bash
cp hosts.csv.sample hosts.csv
# or
export HOSTS_CSV=/path/to/hosts.csv
```

### Error: Browser cannot connect
**Symptom**
- `http://127.0.0.1:5000/v2` does not open.

**Fix**
- Confirm process is running in the same terminal.
- If you changed the port, open the configured port.
- Check `uvicorn` host/port options and the URL path (`/v2`).

## 日本語

### エラー: `NW_DIFF_ENV` 未設定で認証挙動が想定と違う
**症状**
- ローカル開発のつもりなのに、保護エンドポイントが 503 を返す。

**原因**
- `NW_DIFF_ENV` が開発系値（`development`, `dev`, `local`, `test`）になっていない。

**対処**
```bash
export NW_DIFF_ENV=development
```

### エラー: 非開発環境で `NW_DIFF_API_TOKEN` が未設定
**症状**
- API で `Server authentication is not configured` が返る。

**原因**
- 非開発環境では `NW_DIFF_API_TOKEN` 未設定時に保護エンドポイントがブロックされる。

**対処**
```bash
export NW_DIFF_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

### エラー: `DEVICE_PASSWORD` is required
**症状**
- 起動時に `DEVICE_PASSWORD is required` で失敗する。

**対処**
```bash
export DEVICE_PASSWORD=your_device_password
```

### エラー: `hosts.csv` が見つからない
**症状**
- インベントリ不足でホスト一覧やキャプチャが失敗する。

**対処**
```bash
cp hosts.csv.sample hosts.csv
# または
export HOSTS_CSV=/path/to/hosts.csv
```

### エラー: ブラウザから接続できない
**症状**
- `http://127.0.0.1:5000/v2` が開けない。

**対処**
- 同じターミナルでプロセスが起動中か確認する。
- ポートを変えた場合は設定したポートにアクセスする。
- `uvicorn` の host/port 指定と URL パス（`/v2`）を確認する。
