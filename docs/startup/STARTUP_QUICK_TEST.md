# Quick Test Startup / 初見ユーザ向けテスト起動

## Table of Contents
- [English](#english)
  - [Goal](#goal)
  - [Minimal Steps](#minimal-steps)
  - [Success Check](#success-check)
  - [Stop](#stop)
- [日本語](#日本語)
  - [目的](#目的)
  - [最小手順](#最小手順)
  - [成功確認](#成功確認)
  - [停止方法](#停止方法)

## English

### Goal
Run NW-Diff once with the smallest setup to confirm that startup works.

### Minimal Steps
```bash
git clone https://github.com/icecake0141/nw-diff.git
cd nw-diff

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-v2.txt

cp hosts.csv.sample hosts.csv

# Minimal environment for local test
export DEVICE_PASSWORD=dummy
export NW_DIFF_ENV=development

./scripts/start-v2.sh
```

The startup script prints required variables and masks sensitive values before launch.

### Success Check
- Open [http://127.0.0.1:5000/v2](http://127.0.0.1:5000/v2).
- If the v2 page appears, startup succeeded.

### Stop
Press `Ctrl+C` in the terminal.

## 日本語

### 目的
最短手順で一度起動し、環境が動くかを確認するための手順です。

### 最小手順
```bash
git clone https://github.com/icecake0141/nw-diff.git
cd nw-diff

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-v2.txt

cp hosts.csv.sample hosts.csv

# ローカル検証向けの最小環境変数
export DEVICE_PASSWORD=dummy
export NW_DIFF_ENV=development

./scripts/start-v2.sh
```

起動スクリプトは実行前に必須変数を表示し、センシティブな値はマスクします。

### 成功確認
- [http://127.0.0.1:5000/v2](http://127.0.0.1:5000/v2) を開く。
- v2 画面が表示されれば起動成功です。

### 停止方法
ターミナルで `Ctrl+C` を押して停止します。
