# NW-Diff プロジェクト

[![CI](https://github.com/icecake0141/nw-diff/workflows/CI/badge.svg)](https://github.com/icecake0141/nw-diff/actions/workflows/ci.yml)
[![Integration Tests](https://github.com/icecake0141/nw-diff/workflows/Integration%20Tests/badge.svg)](https://github.com/icecake0141/nw-diff/actions/workflows/integration.yml)

NW-Diff は、ネットワークデバイスから収集された設定またはステータスデータを取得、比較、表示するために設計された Flask ベースのウェブアプリケーションです。Netmiko を利用してデバイスに接続し、CSV ファイルに定義されたデータをキャプチャします。diff-match-patch を使用して、2 つのデータセット間の差分を計算し、インライン表示およびサイドバイサイド表示で結果を提示します。差分 HTML ファイルは生成され、専用の "diff" ディレクトリに保存され、後で確認できます。

## 機能

- **デバイス設定:**
  ホスト情報（ホスト名、IP アドレス、SSH ポート、ユーザー名、デバイスモデル）は CSV ファイル (`hosts.csv`) に保持されます。

- **データキャプチャ:**
  2 つのエンドポイントにより各デバイスのデータをキャプチャします:
  - `/capture/origin/<hostname>`: 初期（または元の）データをキャプチャします。
  - `/capture/dest/<hostname>`: 最新（または宛先）のデータをキャプチャします。

  キャプチャされた出力は、それぞれ `origin` と `dest` ディレクトリに保存されます。

- **リアルタイムのセッションログ配信:**
  Netmiko の session_log をタスク単位のログファイルとして保存し、SSE で配信できます:
  - `POST /api/capture/<base>/<hostname>/stream`（バッチは
    `POST /api/capture_all/<base>/stream`）でタスクを開始
  - `GET /api/tasks/<task_id>/stream` に接続してリアルタイム出力を取得
  - `POST /api/tasks/<task_id>/cancel` でタスクをキャンセル
  - ログは既定で `logs/tasks/<task_id>.log` に保存
    (`NW_DIFF_TASK_LOG_DIR` で変更可)
  - `NW_DIFF_TASK_LOG_MAX_FILES`（既定 200）でローテーションし、
    `NW_DIFF_TASK_LOG_RETENTION_SECONDS`（既定 3600）で保持
  - `DEVICE_PASSWORD` や `password=...` の文字列は配信前にマスク

- **設定バックアップ:**
  履歴設定を保持し、データ損失を防ぐため、ファイル上書き前に自動バックアップを作成します:
  - キャプチャ操作時、ファイルが上書きされる前に自動的にバックアップが作成されます
  - ローテーションシステムにより、ファイルごとに最新の10個のバックアップが保持されます
  - バックアップは `backup/` ディレクトリにタイムスタンプ付きで保存されます
  - ファイル名形式: `YYYYMMDD_HHMMSS_hostname-command.txt`
  - 誤った上書きから保護し、履歴設定の追跡を可能にします
  - 必要に応じて古い設定を復元できます

- **差分計算:**
  アプリケーションは、`origin` と `dest` ディレクトリ内の対応するファイルを diff-match-patch を使用して比較します:
  - **インライン表示:** 標準の差分出力を提示します。
  - **サイドバイサイド表示:** 左側に元データ、右側に計算された差分を表示します。

  差分結果は HTML ファイルに変換され、`diff` ディレクトリに保存されます。

- **詳細なデバイス表示:**
  `/host/<hostname>` エンドポイントを通じて各デバイスの詳細情報にアクセスできます。

## ネットワークデバイスコマンドのカスタマイズ

NW-Diff では、ネットワークデバイスで実行されるコマンドをカスタマイズして、設定およびステータスデータをキャプチャできます。このセクションでは、異なるデバイスモデルのコマンドセットを変更または拡張する方法について説明します。

### コマンド設定ファイル

ネットワークデバイスで実行されるコマンドは、`src/nw_diff/devices.py` に定義されています。このファイルには以下が含まれます:

1. **`DEVICE_COMMANDS`** - デバイスモデルとそのコマンドセットをマッピングする辞書
2. **`DEFAULT_COMMANDS`** - デバイスモデルが認識されない場合に使用されるフォールバックコマンド

### コマンド構造の理解

`DEVICE_COMMANDS` 辞書は以下の構造を使用します:

```python
DEVICE_COMMANDS = {
    "fortinet": (
        "get system status",
        "diag switch physical-ports summary",
        "diag switch trunk summary",
        "diag switch trunk list",
        "diag stp vlan list",
    ),
    "cisco": (
        "show version",
        "show running-config",
    ),
    "junos": (
        "show chassis hardware",
        "show route",
    ),
}
```

- **キー**: デバイスモデル名（`hosts.csv` の `model` 列と一致する小文字の文字列）
- **値**: そのモデルのデバイスで実行するコマンド文字列のタプル

### コマンドの変更方法

#### 既存のデバイスモデルへのコマンド追加

既存のデバイスモデルにコマンドを追加するには、`DEVICE_COMMANDS` の対応するタプルを編集します:

```python
# 変更前
"cisco": (
    "show version",
    "show running-config",
),

# 変更後 - "show interfaces status" を追加
"cisco": (
    "show version",
    "show running-config",
    "show interfaces status",
),
```

**重要**: Python タプル構文のため、最後のコマンドの後にカンマを付けてください。

#### 新しいデバイスモデルの追加

新しいデバイスモデルをサポートするには、`DEVICE_COMMANDS` 辞書に新しいエントリを追加します:

```python
DEVICE_COMMANDS = {
    # ... 既存のモデル ...
    "arista": (
        "show version",
        "show running-config",
        "show interfaces status",
    ),
}
```

次に、`hosts.csv` の `model` 列が新しいキー（例: `arista`）と一致することを確認してください。

#### デフォルトコマンドの変更

認識されないデバイスモデルに使用されるフォールバックコマンドを変更する場合は、`DEFAULT_COMMANDS` タプルを編集します:

```python
# 変更前
DEFAULT_COMMANDS = ("show version",)

# 変更後
DEFAULT_COMMANDS = (
    "show version",
    "show system information",
)
```

### ベストプラクティスと安全ガイドライン

1. **最初に手動でコマンドをテストする**
   - `devices.py` にコマンドを追加する前に、デバイスで手動でテストして、正しく動作し、障害を引き起こさないことを確認してください
   - コマンドが **読み取り専用** であり、デバイス設定を変更しないことを確認してください

2. **読み取り専用コマンドを使用する**
   - 情報を取得するコマンドのみを使用してください（例: `show`、`get`、`display`）
   - デバイス設定を変更する可能性のある設定コマンド（例: `config`、`set`、`configure`）は **決して** 使用しないでください
   - デバイスパフォーマンスに影響を与える可能性のあるコマンド（例: 本番環境での `debug` コマンド）は避けてください

3. **コマンド出力サイズを考慮する**
   - 非常に大きな出力を生成するコマンドは、大量のストレージとメモリを消費する可能性があることに注意してください
   - コマンド出力をテストして、管理可能であることを確認してください
   - 必要に応じて、フィルタまたは特定のクエリを使用して出力サイズを制限することを検討してください

4. **デバイスベンダーの規則に従う**
   - 各デバイスベンダーの正しいコマンド構文を使用してください
   - 適切なコマンドの使用法については、ベンダーのドキュメントを参照してください
   - コマンドの特権レベル要件に注意してください

5. **一貫した書式を維持する**
   - コマンドコレクションにはタプル（リストではなく）を使用してください
   - 単一項目のタプルには末尾のカンマを含めてください: `("command",)`
   - `hosts.csv` のエントリと一致するように、デバイスモデルキーには小文字を使用してください

6. **変更を文書化する**
   - 特定のコマンドが追加または変更された理由を説明するコメントを追加してください
   - コンプライアンスまたは監視の目的で重要なコマンドの記録を保持してください

7. **変更前にバックアップする**
   - 変更を加える前に、常に `devices.py` のバックアップを保持してください
   - 本番環境にデプロイする前に、開発環境で変更をテストしてください

### 例: 完全な変更

新しいデバイスモデルを追加し、既存のモデルを変更する完全な例を次に示します:

```python
# src/nw_diff/devices.py 内

DEVICE_COMMANDS = {
    "fortinet": (
        "get system status",
        "diag switch physical-ports summary",
        "diag switch trunk summary",
        "diag switch trunk list",
        "diag stp vlan list",
        # アップリンクステータスの監視のため追加
        "get system interface physical",
    ),
    "cisco": (
        "show version",
        "show running-config",
    ),
    "junos": (
        "show chassis hardware",
        "show route",
    ),
    # 新しいデバイスモデルを追加
    "arista": (
        "show version",
        "show running-config",
        "show interfaces status",
        "show lldp neighbors",
    ),
}

DEFAULT_COMMANDS = ("show version",)
```

### 変更の確認

`devices.py` を変更した後:

1. **構文チェック**: Python 構文の検証を実行
   ```bash
   python -m py_compile src/nw_diff/devices.py
   ```

2. **リンティング**: コード品質をチェック
   ```bash
   pylint src/nw_diff/devices.py
   ```

3. **キャプチャテスト**: アプリケーションが新しいコマンドを実行できることを確認
   - アプリケーションを起動
   - 変更されたモデルを使用するデバイスの `/capture/origin/<hostname>` または `/capture/dest/<hostname>` エンドポイントを使用
   - `origin` または `dest` ディレクトリの出力ファイルを確認
   - エラーがないかログを確認

4. **アプリケーションの再起動**: `devices.py` の変更を有効にするには、アプリケーションの再起動が必要です
   ```bash
   # ローカルで実行している場合
   # 現在のプロセスを停止（Ctrl+C）して再起動
   python run_app.py

   # Docker で実行している場合
   docker-compose restart
   ```

### トラブルシューティング

**コマンドが実行されない:**
- `hosts.csv` のデバイスモデルが `DEVICE_COMMANDS` のキーと一致することを確認してください（大文字小文字は区別されません）
- 接続エラーまたはコマンド失敗については、アプリケーションログを確認してください
- デバイスの認証情報が環境変数で正しいことを確認してください

**構文エラー:**
- タプル構文（末尾のカンマ、適切な括弧）を確認してください
- すべての文字列が適切に引用符で囲まれていることを確認してください
- `python -m py_compile src/nw_diff/devices.py` を実行して構文エラーをチェックしてください

**デバイスでの権限エラー:**
- ユーザーアカウントがコマンドを実行するための十分な特権を持っていることを確認してください
- 一部のコマンドには、有効化モードまたは特定のユーザーロールが必要な場合があります

## インストール

1. **リポジトリのクローン:**
   ```bash
   git clone https://github.com/yourusername/nw-diff.git
   ```
2. **プロジェクトディレクトリに移動:**
   ```bash
   cd nw-diff
   ```

3. **依存関係のインストール:**
   Python がインストールされていることを確認し、必要なパッケージをインストールします:
   ```bash
   pip install -r requirements.txt
   ```
   必要なパッケージには Flask、Netmiko、diff-match-patch が含まれます。

4. **環境変数の設定:**
   - デバイス接続に必要なパスワードを設定するため、`DEVICE_PASSWORD` 環境変数を設定します:
     ```bash
     export DEVICE_PASSWORD=your_device_password
     ```
   - **機密性の高い API エンドポイント（キャプチャ、ログ、エクスポート）を保護するため、`NW_DIFF_API_TOKEN` 環境変数を設定します**:
     ```bash
     export NW_DIFF_API_TOKEN=your_secure_random_token
     ```
     安全なトークンを生成するには:
     ```bash
     python -c "import secrets; print(secrets.token_urlsafe(32))"
     ```

     **重要:** `NW_DIFF_API_TOKEN` が設定されていない場合、機密性の高いエンドポイントは認証なしでアクセス可能になります（本番環境では推奨されません）。

   - **（オプション）ブラウザベースの保護されたエンドポイントへのアクセスに HTTP Basic 認証を設定します**:
     ```bash
     export NW_DIFF_BASIC_USER=your_username
     ```

     **本番環境**では、ハッシュ化されたパスワードを使用します（推奨）:
     ```bash
     # Python を使用してパスワードハッシュを生成
     python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your_password'))"
     export NW_DIFF_BASIC_PASSWORD_HASH='<generated_hash>'
     ```

     **開発環境のみ**では、プレーンパスワードを使用できます（本番環境では推奨されません）:
     ```bash
     export NW_DIFF_BASIC_PASSWORD=your_plain_password
     ```

     **注意:** Basic 認証は `NW_DIFF_API_TOKEN` が設定されている場合にのみ適用されます。保護されたエンドポイントには、Bearer トークン（`Authorization: Bearer <token>`）と Basic 認証（`Authorization: Basic <base64(user:pass)>`）の両方が受け入れられます。

   - **（オプション）ホストインベントリファイルのカスタム場所を指定するため、`HOSTS_CSV` 環境変数を設定します**:
     ```bash
     export HOSTS_CSV=/path/to/hosts.csv
     ```
     設定されていない場合、アプリケーションは現在のディレクトリのデフォルトの `hosts.csv` を使用します。

     **利点:** リポジトリの外にホストインベントリを保存することで、機密データ（IP アドレス、ユーザー名、デバイスモデル）の誤ったコミットを防ぎ、セキュリティが向上します。これは、インベントリをシークレットまたは設定ボリュームとしてマウントできる本番デプロイメントに特に有用です。

     **コンテナの例:**
     ```bash
     docker run -v /secure/path/hosts.csv:/app/hosts.csv -e HOSTS_CSV=/app/hosts.csv ...
     ```

## 使用方法

### 実行モードの概要

アプリケーションは 2 つの主要な実行モードをサポートしています:

1. **ローカル開発モード**: シングルユーザーの開発とテスト用に `127.0.0.1:5000`（localhost のみ）にバインドします。これが安全なデフォルトです。
2. **コンテナ/本番モード**: コンテナネットワークまたはリバースプロキシ（nginx）からのアクセスを許可するために `0.0.0.0:5000` にバインドします。Docker デプロイメントに必要です。

アプリケーションには **ProxyFix ミドルウェア**が含まれており、リバースプロキシ（nginx など）からの `X-Forwarded-*` ヘッダーを正しく処理し、プロキシの背後にデプロイされた場合の適切な URL 生成、HTTPS 検出、クライアント IP ロギングを保証します。

### 本番モードでの実行（デフォルト）

デフォルトでは、セキュリティのため Flask デバッグモードが**無効**になっており、**127.0.0.1**（localhost のみ）にバインドします:

1. **アプリケーションの起動:**
   ```bash
   python run_app.py
   ```
   またはソースから直接:
   ```bash
   PYTHONPATH=src python -m nw_diff.app
   ```
2. **アプリケーションへのアクセス:**
   ブラウザで [http://localhost:5000](http://localhost:5000) にアクセスします。

### 開発モードでの実行

ローカル開発では、`APP_DEBUG` 環境変数を設定してデバッグモードを有効にできます:

1. **デバッグモードで実行:**
   ```bash
   export APP_DEBUG=true
   python run_app.py
   ```
   またはインラインで実行:
   ```bash
   APP_DEBUG=true python run_app.py
   ```
2. **アプリケーションへのアクセス:**
   ブラウザで [http://localhost:5000](http://localhost:5000) にアクセスします。

**注意:** デバッグモードは機密情報を公開しセキュリティ脆弱性を生む可能性があるため、本番環境では**決して**有効にしないでください。

### バインドホストとポートのカスタマイズ

環境変数を使用してバインドホストとポートをカスタマイズできます:

- `FLASK_RUN_HOST`: バインドするホスト（デフォルト: ローカル開発用に `127.0.0.1`）
- `FLASK_RUN_PORT`: バインドするポート（デフォルト: `5000`）

**例:**

```bash
# すべてのインターフェースにバインド（コンテナ環境で有用）
FLASK_RUN_HOST=0.0.0.0 python run_app.py

# 異なるポートを使用
FLASK_RUN_PORT=8080 python run_app.py

# 複数の設定を組み合わせる
FLASK_RUN_HOST=0.0.0.0 FLASK_RUN_PORT=8080 APP_DEBUG=false python run_app.py
```

**セキュリティ注意:** リバースプロキシなしでローカルで実行する場合は、不正なネットワークアクセスを防ぐためにデフォルトの `127.0.0.1` を使用してください。コンテナ環境内または適切に設定された認証付きリバースプロキシの背後でのみ `0.0.0.0` を使用してください。

### エンドポイントとの連携

#### 公開エンドポイント（認証不要）
- **ホスト一覧の表示:** `/`（ホームページ）
- **詳細なデバイス情報の表示:** `/host/<hostname>`
- **ファイルの比較:** `/compare_files`

#### 保護されたエンドポイント（認証が必要）
以下のエンドポイントは `NW_DIFF_API_TOKEN` が設定されている場合に認証が必要です。Bearer トークンと Basic 認証の両方がサポートされています:
- **データキャプチャ:**
  - 元データ: `/capture/origin/<hostname>`
  - 宛先データ: `/capture/dest/<hostname>`
  - 全デバイス: `/capture_all/origin` または `/capture_all/dest`
- **ログの表示:**
  - Web UI: `/logs`
  - API: `/api/logs`
- **データのエクスポート:**
  - HTML エクスポート: `/export/<hostname>`
  - JSON API: `/api/export/<hostname>`

**Bearer トークンを使用した curl の例:**
```bash
curl -H "Authorization: Bearer your_token_here" http://localhost:5000/api/logs
```

**Basic 認証を使用した curl の例:**
```bash
curl -u username:password http://localhost:5000/api/logs
```

**ブラウザを使用した例:**
ブラウザで保護されたエンドポイントにアクセスする場合、Basic 認証が設定されていれば、ユーザー名とパスワードの入力を求められます。ブラウザは自動的に資格情報を Basic 認証ヘッダーとしてエンコードします。

**注意:** `NW_DIFF_API_TOKEN` が設定されていない場合、これらのエンドポイントは認証なしで動作します（本番環境では推奨されません）。

### 差分結果の確認

計算された差分 HTML ファイルは `diff` ディレクトリに保存され、オフラインで確認できます。

## Docker デプロイメント

NW-Diff は Docker と docker-compose を介した HTTPS（TLS 終端）およびオプションの Basic 認証を使用したコンテナ化デプロイメントをサポートしています。これにより、安全で本番環境に対応したデプロイメントオプションが提供されます。

**アーキテクチャ概要:**
- **nginx**: TLS 終端を伴うリバースプロキシとして機能し、`X-Forwarded-*` ヘッダーを設定します
- **Flask アプリ**: ProxyFix ミドルウェアを使用して、転送されたヘッダーを正しく解釈します
- **コンテナバインディング**: Flask はコンテナ内で `0.0.0.0:5000` にバインドします（`FLASK_RUN_HOST` 経由で設定）
- **ネットワーク分離**: nginx のみがホストに公開され、Flask アプリは Docker ネットワーク内でのみアクセス可能です

ProxyFix ミドルウェアにより、Flask アプリが nginx リバースプロキシの背後で実行されている場合に、元のリクエストプロトコル（HTTPS）、ホスト、クライアント IP を正しく検出できます。

### 前提条件

- Docker と Docker Compose がインストールされていること
- OpenSSL（自己署名証明書の生成用）
- Apache Utils（htpasswd ファイルの生成用） - `apt-get install apache2-utils` または `yum install httpd-tools`

### クイックスタート

1. **リポジトリのクローンとプロジェクトディレクトリへの移動:**
   ```bash
   git clone https://github.com/icecake0141/nw-diff.git
   cd nw-diff
   ```

2. **環境変数の設定:**
   ```bash
   cp .env.example .env
   # .env を編集して DEVICE_PASSWORD と NW_DIFF_API_TOKEN を設定
   ```

3. **TLS 証明書と Basic 認証の生成（自動化）:**

   **オプション A: 自動セットアップ（CI/CD に推奨）**
   ```bash
   # 環境変数を設定
   export NW_DIFF_BASIC_USER=admin
   export NW_DIFF_BASIC_PASSWORD=your_strong_password
   export CERT_HOSTNAME=myserver.example.com  # オプション、デフォルトは localhost

   # 自動初期化スクリプトを実行
   ./docker/nginx/init-certs-and-htpasswd.sh
   ```
   このスクリプトは以下を実行します:
   - 自己署名 TLS 証明書を生成（開発/デモ用）
   - 提供された資格情報で .htpasswd ファイルを作成
   - ファイル権限と設定を検証
   - セキュリティ警告とリマインダーを表示

   **オプション B: 対話型セットアップ**
   ```bash
   # 証明書を対話的に生成
   ./scripts/mk-certs.sh
   # プロンプトに従って証明書を生成
   # またはホスト名を指定: CERT_HOSTNAME=myserver.example.com ./scripts/mk-certs.sh

   # Basic 認証資格情報を対話的に生成
   ./scripts/mk-htpasswd.sh
   # プロンプトに従ってユーザー名/パスワードを作成
   ```

4. **hosts.csv インベントリファイルの作成:**
   ```bash
   cp hosts.csv.sample hosts.csv
   # デバイス情報で hosts.csv を編集
   ```

5. **アプリケーションスタックの起動:**
   ```bash
   docker-compose up -d
   ```

6. **アプリケーションへのアクセス:**
   - HTTPS: `https://localhost/`（自己署名証明書の警告を受け入れる必要があります）
   - Basic 認証資格情報の入力を求められます

7. **ログの表示:**
   ```bash
   docker-compose logs -f
   ```

8. **アプリケーションの停止:**
   ```bash
   docker-compose down
   ```

### 設定

#### 環境変数

`.env` ファイルで以下を設定します:

- `DEVICE_PASSWORD`: ネットワークデバイスへの SSH 接続用パスワード
- `NW_DIFF_API_TOKEN`: API 認証用の安全なトークン（`python -c "import secrets; print(secrets.token_urlsafe(32))"` で生成）
- `NW_DIFF_BASIC_USER`: （オプション）HTTP Basic 認証用のユーザー名
- `NW_DIFF_BASIC_PASSWORD_HASH`: （オプション）Basic 認証用のハッシュ化されたパスワード（`python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('password'))"` で生成）
- `NW_DIFF_BASIC_PASSWORD`: （オプション）Basic 認証用のプレーンパスワード（開発のみ - 本番環境ではハッシュ化されたパスワードを使用）
- `APP_DEBUG`: 本番環境では `false` に設定（デフォルト）
- `HOSTS_CSV`: ホストインベントリファイルへのオプションのカスタムパス

**認証モード:**
- `NW_DIFF_API_TOKEN` が設定されていない場合: 認証不要（レガシーモード）
- `NW_DIFF_API_TOKEN` が設定されている場合:
  - API クライアントは Bearer トークンを使用可能: `Authorization: Bearer <token>`
  - ブラウザユーザーは Basic 認証を使用可能: `Authorization: Basic <base64(user:pass)>`
  - 保護されたエンドポイント（キャプチャ、ログ、エクスポート）には両方の方法が受け入れられます

#### TLS/SSL 証明書

**開発/テスト用**には、提供されたスクリプトを使用して自己署名証明書を生成します:
```bash
./scripts/mk-certs.sh
```

**本番環境**では以下を行う必要があります:
- 信頼された認証局（CA）からの証明書を使用するか、または
- Caddy または certbot で Let's Encrypt を使用するか、または
- 既存の証明書をマウントします:
  ```bash
  # 証明書を docker/certs/ に配置
  cp /path/to/your/cert.pem docker/certs/cert.pem
  cp /path/to/your/key.pem docker/certs/key.pem
  chmod 644 docker/certs/cert.pem
  chmod 600 docker/certs/key.pem
  ```

#### Basic 認証

Basic 認証はデフォルトですべてのエンドポイントで有効です。ユーザーを管理するには:

**ユーザーを追加:**
```bash
./scripts/mk-htpasswd.sh
```

**追加ユーザーを追加:**
```bash
htpasswd docker/.htpasswd <username>
```

**Basic 認証を無効化（本番環境では推奨されません）:**
`docker/nginx.conf` を編集して以下の行をコメントアウトします:
```nginx
# auth_basic "NW-Diff Access";
# auth_basic_user_file /etc/nginx/.htpasswd;
```
その後再起動: `docker-compose restart nginx`

#### 永続データ

永続ストレージには Docker ボリュームが使用されます:
- `nw-diff-logs`: アプリケーションログ
- `nw-diff-dest`: 宛先設定スナップショット
- `nw-diff-origin`: 元の設定スナップショット
- `nw-diff-diff`: 生成された差分ファイル
- `nw-diff-backup`: 設定バックアップ

データをバックアップまたは移行するには:
```bash
# ボリュームのバックアップ
docker run --rm -v nw-diff-logs:/data -v $(pwd):/backup alpine tar czf /backup/nw-diff-logs-backup.tar.gz -C /data .

# ボリュームの復元
docker run --rm -v nw-diff-logs:/data -v $(pwd):/backup alpine tar xzf /backup/nw-diff-logs-backup.tar.gz -C /data
```

### セキュリティのベストプラクティス

#### 概要
NW-Diff はセキュリティを優先して設計されていますが、適切なデプロイメントには慎重な設定が必要です。このセクションでは、本番デプロイメントの重要なセキュリティ対策について概説します。

#### TLS/SSL 証明書

**開発/デモ環境:**
- 提供された自己署名証明書生成を使用:
  ```bash
  ./scripts/mk-certs.sh
  # または自動セットアップ用
  ./docker/nginx/init-certs-and-htpasswd.sh
  ```
- ブラウザのセキュリティ警告を受け入れる（自己署名証明書では予想される）
- 本番環境では自己署名証明書を**決して**使用しないでください

**本番環境:**
- **推奨**: Let's Encrypt（無料、自動化、広く信頼されている）
  - certbot または類似ツールを使用して自動更新
  - certbot の例:
    ```bash
    certbot certonly --standalone -d yourdomain.com
    cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem docker/certs/cert.pem
    cp /etc/letsencrypt/live/yourdomain.com/privkey.pem docker/certs/key.pem
    ```
- **代替**: 商用 CA（DigiCert、Sectigo、GlobalSign など）
- **エンタープライズ**: 内部 PKI/CA インフラストラクチャ
- **重要**: 信頼された証明書をインストールした後、`docker/nginx.conf` で HSTS を有効にします:
  ```nginx
  add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
  ```
- **警告**: 自己署名証明書で HSTS を有効にしないでください - 永続的なブラウザの問題を引き起こします

#### 認証と認可

**API トークンセキュリティ:**
1. 強力でランダムなトークンを生成:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
2. 環境変数またはシークレットマネージャーに保存（コードには決して保存しない）
3. 開発/ステージング/本番環境で異なるトークンを使用
4. 定期的にトークンをローテーション（90 日ごとを推奨）
5. トークンを含む `.env` ファイルを決してコミットしない

**Basic 認証:**
1. 強力なパスワードを使用（最低 12 文字、大文字小文字、数字、記号を混在）
2. ハッシュ化されたパスワードを生成:
   ```bash
   ./scripts/mk-htpasswd.sh
   # または自動デプロイメント用
   export NW_DIFF_BASIC_USER=admin
   export NW_DIFF_BASIC_PASSWORD=your_strong_password
   ./docker/nginx/init-certs-and-htpasswd.sh
   ```
3. `docker/.htpasswd` をバージョン管理に**決して**コミットしない（`.gitignore` でカバー）
4. 可能であればアカウントロックアウトポリシーを実装（nginx モジュールまたは WAF 経由）

**デバイス資格情報:**
1. `DEVICE_PASSWORD` を安全に保存（シークレットマネージャー、暗号化されたボールト）
2. 可能な場合はネットワークデバイスで読み取り専用アカウントを使用
3. サポートされている場合はパスワードの代わりに SSH キー認証を実装
4. デバイス資格情報を定期的にローテーション

#### ネットワークセキュリティ

1. **ファイアウォール設定:**
   - HTTPS（443）アクセスを承認されたネットワーク/IP に制限
   - 不要な場合は HTTP（80）ポートを閉じる（オプション、デフォルトで HTTPS にリダイレクト）
   - リモートアクセスには VPN またはバスティオンホストを使用

2. **リバースプロキシの強化:**
   - nginx 設定にはデフォルトでレート制限が含まれています
   - 使用パターンに基づいて `docker/nginx.conf` でレート制限を調整:
     ```nginx
     limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;
     limit_req_zone $binary_remote_addr zone=api:10m rate=5r/s;
     ```
   - 追加保護のために WAF（Web Application Firewall）の追加を検討

3. **コンテナセキュリティ:**
   - 可能な場合はコンテナを非 root ユーザーとして実行
   - 環境変数の代わりに機密データに Docker シークレットを使用
   - 定期的にコンテナイメージの脆弱性をスキャン:
     ```bash
     docker scan nw-diff:latest
     ```

#### データ保護

1. **機密ファイルの処理:**
   - `.gitignore` が以下を除外することを確認: `docker/.htpasswd`、`docker/certs/`、`.env`、`hosts.csv`
   - 本番環境ではデバイスインベントリ（`hosts.csv`）をリポジトリ外に保存
   - 機密データにはボリュームマウントを使用:
     ```bash
     docker run -v /secure/path/hosts.csv:/app/hosts.csv:ro -e HOSTS_CSV=/app/hosts.csv ...
     ```

2. **シークレット管理:**
   - 環境固有のシークレットを使用（開発 vs. 本番）
   - Docker シークレット、Kubernetes シークレット、または専用シークレットマネージャー（HashiCorp Vault、AWS Secrets Manager など）の使用を検討
   - エラーメッセージでシークレットをログまたは公開しない

3. **設定バックアップ:**
   - 設定データのバックアップを暗号化
   - 安全でアクセス制御されたロケーションにバックアップを保存
   - コンプライアンスのための保持ポリシーを実装

#### モニタリングと監査

1. **ログ管理:**
   - nginx アクセス/エラーログを定期的に確認:
     ```bash
     docker-compose logs nginx | grep -E "40[134]|50[0-3]"
     ```
   - 疑わしいアクティビティを監視: 繰り返される 401/403 エラー、異常なトラフィックパターン
   - 集中ログ（ELK スタック、Splunk など）を検討

2. **セキュリティ監査:**
   - 定期的にセキュリティスキャンを実行:
     ```bash
     pip-audit -r requirements.txt
     docker scan nw-diff:latest
     ```
   - 四半期ごとに依存関係を確認して更新
   - Flask、nginx、依存関係のセキュリティアドバイザリを購読

3. **アクセス監視:**
   - すべてのキャプチャ操作と設定変更をログ
   - 不正アクセス試行のアラートを実装
   - 定期的なアクセスレビュー（資格情報、トークンなどを持つユーザー）

#### 定期的なメンテナンス

1. **更新:**
   - ベース Docker イメージを最新に保つ: `docker-compose pull`
   - Python 依存関係を更新: `pip install -r requirements.txt --upgrade`
   - セキュリティアドバイザリと CVE を監視

2. **証明書の更新:**
   - Let's Encrypt 証明書は 90 日ごとに期限切れ - 更新を自動化
   - 手動証明書更新のカレンダーリマインダーを設定
   - 定期的に証明書の有効性をテスト:
     ```bash
     openssl x509 -in docker/certs/cert.pem -noout -enddate
     ```

3. **資格情報のローテーション:**
   - 90 日ごとに API トークンをローテーション
   - 180 日ごとに Basic 認証パスワードを更新
   - 組織のポリシーに従ってデバイスパスワードを変更

#### 本番デプロイメントチェックリスト

本番環境にデプロイする前に確認:

- [ ] 信頼された TLS 証明書を使用（自己署名ではない）
- [ ] `docker/nginx.conf` で HSTS ヘッダーが有効
- [ ] すべての認証に強力で一意のパスワード
- [ ] API トークンが生成され安全に保存されている
- [ ] `.env` ファイルがバージョン管理にコミットされていない
- [ ] `hosts.csv` がリポジトリ外に保存されているか適切に保護されている
- [ ] アクセスを制限するファイアウォールルールが設定されている
- [ ] コンテナイメージの脆弱性がスキャンされている
- [ ] ログが収集され監視されている
- [ ] バックアップ戦略が実装されテストされている
- [ ] デバッグモードが無効（`APP_DEBUG=false`）
- [ ] すべての依存関係の最新安定バージョンを実行
- [ ] インシデント対応計画が文書化されている

#### デモ vs. 本番設定

**デモ/開発環境:**
- 自己署名証明書が許容される
- HSTS が無効（コメントアウト）
- Basic 認証はオプション
- ローカルテスト用に `127.0.0.1` にバインド
- デバッグモードを一時的に有効にできる
- より緩やかなレート制限

**本番環境:**
- 信頼された TLS 証明書を**使用する必要があります**
- HSTS ヘッダーを**有効にする必要があります**
- Basic 認証 + API トークンを**使用する必要があります**
- コンテナ内でのみ `0.0.0.0` にバインド（nginx プロキシ）
- デバッグモードを**無効にする必要があります**
- 厳格なレート制限と監視
- 定期的なセキュリティ監査と更新

#### セキュリティ問題の報告

NW-Diff でセキュリティ脆弱性を発見した場合:
1. 公開 GitHub issue を**開かない**
2. リポジトリメンテナーにセキュリティ上の懸念をプライベートにメール
3. 詳細な情報を含める: 再現手順、影響評価
4. 公開開示前に修正のための合理的な時間を許可

### トラブルシューティング

**ブラウザでの証明書エラー:**
- 自己署名証明書は警告を表示します - これは開発では予想されます
- ブラウザで例外を追加するか、システム信頼ストアに証明書をインポート（scripts/mk-certs.sh の出力を参照）

**接続拒否:**
- コンテナが実行されていることを確認: `docker-compose ps`
- ログを確認: `docker-compose logs`

**認証失敗:**
- .htpasswd ファイルが存在することを確認: `ls -la docker/.htpasswd`
- 資格情報をテスト: `htpasswd -v docker/.htpasswd <username>`

**権限エラー:**
- 証明書ファイルに正しい権限があることを確認（cert.pem: 644、key.pem: 600）
- ボリューム権限を確認: `docker-compose exec nw-diff ls -la /app`

**Docker ビルド SSL 証明書エラー:**
- SSL インターセプトを伴う企業/CI 環境でビルドする場合は、以下を使用:
  ```bash
  docker build --build-arg SKIP_PIP_SSL_VERIFY=1 -t nw-diff:latest .
  ```
- これにより、pip インストール中に PyPI ドメインの `--trusted-host` フラグが追加されます
- **注意:** 信頼できる環境でのみこの回避策を使用してください; SSL 検証をバイパスします

## 開発

### ローカル開発セットアップ

1. **開発用依存関係のインストール:**
   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   ```

2. **セキュリティ監査の実行:**
   ```bash
   pip-audit -r requirements.txt -r requirements-dev.txt
   ```

3. **フォーマット、lint、型チェック、テスト:**
   ```bash
   black src tests
   pylint src tests
   mypy src tests
   pytest
   ```

4. **pre-commit フックの実行:**
   ```bash
   pre-commit run --all-files
   ```

### テスト

NW-Diff には品質とセキュリティを保証するための包括的なテストカバレッジが含まれています:

#### ユニットおよび統合テスト

ローカルで完全なテストスイートを実行:
```bash
pytest -v
```

テストスイートには以下が含まれます:
- **ユニットテスト**: コアアプリケーションロジック、認証、認可
- **統合テスト**: Docker デプロイメント設定、セキュリティ設定
- **型チェック**: mypy による静的型分析
- **Lint**: pylint によるコード品質チェック
- **フォーマット**: black によるコードスタイル検証

#### フルスタック統合テスト（CI）

プロジェクトには完全な Docker Compose デプロイメントを検証する自動エンドツーエンドテストが含まれています:

**テストされる内容:**
- ✅ Docker Compose が正常にビルドされる
- ✅ HTTPS（TLS/SSL）が有効で機能している
- ✅ HTTP が正しく HTTPS にリダイレクトされる
- ✅ Basic 認証が必要で機能している
- ✅ 保護されたエンドポイントでの Bearer トークン認証
- ✅ 無効な資格情報が拒否される（401 応答）
- ✅ 有効な資格情報がアクセスを許可する（200 応答）
- ✅ 自己署名証明書が正しく生成される
- ✅ すべてのセキュリティヘッダーが存在する
- ✅ サービスが正常に開始され安定したままである

**統合テストをローカルで実行:**

1. **スタックのセットアップと起動:**
   ```bash
   # 証明書と .htpasswd を生成
   export NW_DIFF_BASIC_USER=admin
   export NW_DIFF_BASIC_PASSWORD=yourpassword
   ./docker/nginx/init-certs-and-htpasswd.sh

   # hosts.csv を作成（またはサンプルからコピー）
   cp hosts.csv.sample hosts.csv

   # .env で環境変数を設定
   cp .env.example .env
   # 値で .env を編集

   # スタックを起動
   docker-compose up -d
   ```

2. **統合テストスクリプトを実行:**
   ```bash
   export NW_DIFF_BASIC_USER=admin
   export NW_DIFF_BASIC_PASSWORD=yourpassword
   export NW_DIFF_API_TOKEN=your_token_here
   ./scripts/test-integration.sh
   ```

3. **クリーンアップ:**
   ```bash
   docker-compose down -v
   ```

#### 継続的インテグレーション

プロジェクトはすべてのプッシュとプルリクエストで自動テストのために GitHub Actions を使用します:

- **CI ワークフロー**（`.github/workflows/ci.yml`）: ユニットテスト、lint、型チェック、セキュリティ監査を実行
- **統合ワークフロー**（`.github/workflows/integration.yml`）: HTTPS と認証検証を伴うフルスタック Docker Compose テストを実行

テスト結果を表示: [GitHub Actions](https://github.com/icecake0141/nw-diff/actions)

#### テストカバレッジ

テストは以下をカバーします:
- Flask アプリケーションのルートと認証ロジック
- Docker と nginx の設定検証
- TLS/SSL 証明書のセットアップと検証
- Basic 認証と Bearer トークンフロー
- セキュリティヘッダーと HTTP ステータスコード
- ファイル権限と .gitignore ルール
- SPDX ライセンスヘッダーと LLM 帰属

#### テストの記述

貢献する場合は、以下をお願いします:
- 新機能またはバグ修正のテストを追加
- PR を提出する前にすべてのテストがローカルで合格することを確認
- `tests/` ディレクトリの既存のテストパターンに従う
- テストファイルに SPDX ヘッダーと LLM 帰属を含める
- ポジティブケースとネガティブケースの両方をテスト（成功と失敗のシナリオ）

### Pre-commit フック

コード品質を保証するために pre-commit フックを実行:
```bash
pre-commit run --all-files
```
