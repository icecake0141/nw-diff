<!--
Copyright 2025 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.
-->
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Docker-based deployment support with production-ready Dockerfile
- Docker Compose configuration for orchestrating application and reverse proxy
- HTTPS/TLS termination via nginx reverse proxy
- Basic Authentication support at the reverse proxy level
- Helper script (`scripts/mk-certs.sh`) for generating self-signed TLS certificates
- Helper script (`scripts/mk-htpasswd.sh`) for managing Basic Auth credentials
- Comprehensive Docker deployment documentation in README.md
- Integration tests for Docker deployment and configuration validation
- Environment variable configuration via `.env.example`
- Persistent Docker volumes for logs, configurations, and diffs
- Security headers and rate limiting in nginx configuration
- Health check endpoints for container orchestration
- Multi-stage Docker build for optimized image size
- Non-root user execution in Docker container for enhanced security
- `scripts/report-local-diff.sh` to inventory mixed worktree changes before commit split
- `scripts/run-v2-ci-postchecks.sh` shared CI post-check bundle for readiness/locks/cutover/summary
- v2 contract summary tool tests for missing/malformed artifact inputs
- Context-only diff view toggle for host detail (v1/v2) with configurable context lines

### Changed
- Updated `.gitignore` to exclude Docker-generated files (certificates, htpasswd)
- Updated `.gitignore` to ignore `.pylint_cache/`
- Hardened `scripts/check-v2-contract.sh` to send auth headers for protected v2 endpoints
- Hardened `scripts/summarize-v2-contract.sh` to tolerate malformed JSON artifacts
- Refactored v2 auth parser to reduce lint suppressions while preserving behavior
- Documented v2 auth and CI fallback behavior in runbook
- Deduplicated duplicated CI post-check logic in both `ci.yml` and `integration.yml`

### Security
- Enforced HTTPS by default with HTTP to HTTPS redirection
- Added configurable Basic Authentication for all endpoints
- Implemented security headers (X-Frame-Options, X-Content-Type-Options, X-XSS-Protection)
- Added rate limiting for general and API endpoints
- Non-root user execution in Docker containers
- Secure credential management via environment variables and external files

## 日本語訳

# 変更履歴

このファイルには、このプロジェクトの主な変更点を記録します。

形式は [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) に基づき、
このプロジェクトは [Semantic Versioning](https://semver.org/spec/v2.0.0.html) に準拠します。

## [Unreleased]

### 追加
- 本番運用を想定した Dockerfile による Docker デプロイ対応
- アプリケーションとリバースプロキシを連携させる Docker Compose 設定
- nginx リバースプロキシによる HTTPS/TLS 終端
- リバースプロキシ層での Basic 認証サポート
- 自己署名 TLS 証明書生成用ヘルパースクリプト（`scripts/mk-certs.sh`）
- Basic 認証情報管理用ヘルパースクリプト（`scripts/mk-htpasswd.sh`）
- README.md に Docker デプロイの包括的ドキュメントを追加
- Docker デプロイと構成検証の統合テスト
- `.env.example` による環境変数設定
- ログ、設定、差分を永続化する Docker ボリューム
- nginx 設定でのセキュリティヘッダーとレート制限
- コンテナオーケストレーション向けヘルスチェックエンドポイント
- 画像サイズ最適化のためのマルチステージ Docker ビルド
- セキュリティ向上のため Docker コンテナを非 root ユーザーで実行
- コミット分割前にワークツリーの混在差分を棚卸しする `scripts/report-local-diff.sh`
- readiness/locks/cutover/summary をまとめた共通 CI 後処理バンドル `scripts/run-v2-ci-postchecks.sh`
- 欠損/不正なアーティファクト入力に対する v2 契約サマリーツールのテスト
- ホスト詳細画面（v1/v2）のコンテキスト表示切替と前後行数の調整

### 変更
- Docker 生成ファイル（証明書、htpasswd）を除外するよう `.gitignore` を更新
- `.pylint_cache/` を無視するよう `.gitignore` を更新
- 保護された v2 エンドポイント向け認証ヘッダー送信に対応するため `scripts/check-v2-contract.sh` を強化
- 不正な JSON アーティファクトを許容するよう `scripts/summarize-v2-contract.sh` を強化
- 挙動を維持しつつ lint 抑制を減らすため v2 認証パーサーをリファクタリング
- v2 認証と CI フォールバック挙動をランブックに追記
- `ci.yml` と `integration.yml` の重複した CI 後処理ロジックを統合

### セキュリティ
- HTTP から HTTPS へのリダイレクトにより HTTPS をデフォルトで強制
- 全エンドポイント向けの設定可能な Basic 認証を追加
- セキュリティヘッダー（X-Frame-Options、X-Content-Type-Options、X-XSS-Protection）を実装
- 一般エンドポイントと API エンドポイントにレート制限を追加
- Docker コンテナを非 root ユーザーで実行
- 環境変数および外部ファイルによる安全な認証情報管理
