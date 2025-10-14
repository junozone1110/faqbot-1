# 法律FAQ Bot（ハイブリッド検索版）

Google Drive上のPDFファイルから法律FAQボットを作成するアプリケーションです。
RAG（Retrieval-Augmented Generation）とハイブリッド検索（BM25 + ベクトル検索）を使用して、PDFの内容に基づいて質問に回答します。

## 🎯 主な機能

### 検索・回答機能
- **ハイブリッド検索**: BM25（キーワード検索）とベクトル検索を組み合わせた高精度検索
- **メタデータフィルタリング**: 選択された法律に関連するドキュメントのみを検索
- **参照元表示**: 回答の根拠となる参照文書を明示
- **要約表示**: 最も関連性の高い文書からの要約を自動生成

### 対話機能
- **法律選択**: 4つの法律から選択可能
  - 景表法（不当景品類及び不当表示防止法）
  - 資金決済法
  - 個人情報保護法
  - 印紙税法
- **質問の具体性チェック**: 曖昧な質問を自動検知し、追加ヒアリングを実施
- **スレッド内対話継続**: ユーザーの追加情報を自動認識し、質問を段階的に具体化
- **インタラクティブボタン**: Slackのボタンで直感的に操作可能

### Slack統合
- **メンション対応**: `@faq-bot 質問` で起動
- **スレッド返信**: 会話の流れを整理
- **メンションなし応答**: スレッド内では追加の`@`メンション不要

## 📋 前提条件

- Python 3.9以上
- Google Cloud Platform アカウント
- Slack Workspace（管理者権限）
- OpenAI APIキー
- Google Gemini APIキー

## 🚀 セットアップ

### 1. Python環境の構築

```bash
python -m venv venv
source venv/bin/activate  # Mac/Linux
# または
venv\Scripts\activate  # Windows
```

### 2. 必要ライブラリのインストール

```bash
pip install -r requirements.txt
```

### 3. Google Cloud Platformの設定

1. [Google Cloud Console](https://console.cloud.google.com/)で新しいプロジェクトを作成
2. Google Drive APIを有効化
3. 認証情報（OAuth 2.0 クライアントID）を作成
   - アプリケーションの種類: デスクトップアプリ
   - JSONファイルをダウンロードし、`credentials.json`として保存

### 4. Slack Appの設定

詳細は [SLACK_SETUP.md](SLACK_SETUP.md) を参照してください。

主な手順:
1. [Slack API](https://api.slack.com/apps)で新しいAppを作成
2. **OAuth & Permissions**で以下のスコープを追加:
   - `app_mentions:read`
   - `channels:history`
   - `channels:read`
   - `chat:write`
   - `im:history`
   - `im:read`
   - `im:write`
3. **Event Subscriptions**で以下のイベントを購読:
   - `app_mention`
   - `message.channels`
   - `message.im`
4. **Socket Mode**を有効化
5. トークンを取得:
   - Bot Token (`xoxb-...`)
   - App Token (`xapp-...`)

### 5. 環境変数の設定

`.env.example`をコピーして`.env`ファイルを作成し、必要な情報を入力します。

```bash
cp .env.example .env
```

`.env`ファイルを編集：

```env
# Google Drive設定
GOOGLE_DRIVE_FOLDER_ID="あなたのDriveフォルダID"

# API Keys
GOOGLE_API_KEY="あなたのGemini APIキー"
OPENAI_API_KEY="あなたのOpenAI APIキー"

# Slack設定
SLACK_BOT_TOKEN="xoxb-your-bot-token"
SLACK_APP_TOKEN="xapp-your-app-token"
```

**各項目の取得方法:**

- **Google DriveフォルダID**: 
  - Google DriveでフォルダのURLを確認
  - `https://drive.google.com/drive/folders/FOLDER_ID` の `FOLDER_ID` 部分

- **Gemini APIキー**: 
  - [Google AI Studio](https://makersuite.google.com/app/apikey)でAPIキーを作成

- **OpenAI APIキー**: 
  - [OpenAI Platform](https://platform.openai.com/api-keys)でAPIキーを作成

- **Slack トークン**: 
  - Slack App設定ページから取得（上記参照）

## 🐳 Docker での実行（推奨）

Dockerを使用すると、環境構築が簡単で、どこでも同じ環境で動作します。

### 前提条件

- Docker
- Docker Compose

### セットアップと実行

1. **環境変数ファイルを作成**

```bash
cp .env.example .env
# .envファイルを編集して必要な情報を入力
```

2. **認証情報を配置**

```bash
# Google Cloud Platformから取得したcredentials.jsonを配置
cp /path/to/your/credentials.json ./credentials.json
```

3. **ベクトルDBを準備（初回のみ）**

```bash
docker-compose --profile setup run --rm prepare-db
```

初回実行時、ブラウザでGoogle認証が求められます。認証後、`token.json`が自動生成されます。

4. **Botを起動**

```bash
docker-compose up -d
```

バックグラウンドで起動します。

5. **ログを確認**

```bash
docker-compose logs -f
```

6. **停止**

```bash
docker-compose down
```

### Docker環境のトラブルシューティング

**コンテナの状態確認**
```bash
docker-compose ps
```

**コンテナに入る**
```bash
docker-compose exec faq-bot bash
```

**ログの確認**
```bash
docker-compose logs faq-bot --tail=100
```

**完全にクリーンアップして再ビルド**
```bash
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

## 📖 使い方（ローカル実行）

### ステップ1: データベースの準備

Google DriveからPDFをダウンロードし、ベクトルDBを作成します。

```bash
python prepare_database_openai.py
```

初回実行時、ブラウザで認証が求められます。

**処理内容:**
- Google DriveからPDF取得
- PDFをチャンク分割
- OpenAIのtext-embedding-3-largeで埋め込み生成
- ChromaDBに保存

### ステップ2: Slack Botの起動

```bash
python slack_bot_hybrid.py
```

起動メッセージが表示されたら準備完了です：

```
============================================================
✓ FAQ Bot (ハイブリッド検索版) が起動しました
============================================================
チャネルで @FAQ Bot をメンションして質問してください
対応法律: 景表法、資金決済法、個人情報保護法、印紙税法
BM25 + ベクトル検索 + メタデータフィルタリング
============================================================
⚡️ Bolt app is running!
```

### ステップ3: Slackで質問

#### 基本的な使い方

1. Slackチャネルで`@faq-bot`をメンション
```
@faq-bot 景品類の定義を教えてください
```

2. 法律選択ボタンが表示されるので、該当する法律を選択

3. 回答が返されます

#### 曖昧な質問の場合

1. 曖昧な質問をする
```
@faq-bot 電子チケットを発行する場合、資金決済法の適用はありますか？
```

2. 法律を選択（例: 資金決済法）

3. 追加質問が返される
```
❓ 質問を具体化させてください

1. 電子チケットの金額はいくらですか？
2. 誰が発行しますか（事業者/個人）？
3. どのような用途で使用できますか？
```

4. **スレッド内で**追加情報を提供（`@faq-bot`なしでOK）
```
5000円のチケットで、当社（ECサイト運営会社）が発行します。
自社サイトでの商品購入に使用できます。
```

5. 情報が十分なら回答、不足していればさらに質問が返される

## 🛠️ コマンドラインでのテスト

Slackを使わずにコマンドラインでテストする場合：

```bash
python ask_question_hybrid.py
```

対話形式で質問できます。

## 📁 ファイル構成

```
09_faq-bot/
├── prepare_database_openai.py    # ベクトルDB作成（OpenAI埋め込み）
├── slack_bot_hybrid.py            # Slack Bot（ハイブリッド検索版）
├── ask_question_hybrid.py         # CLI版（ハイブリッド検索版）
├── hybrid_search.py               # ハイブリッド検索実装
├── check_vectordb.py              # ベクトルDB内容確認ツール
├── requirements.txt               # 必要なライブラリ
├── .env                           # 環境変数（要作成）
├── .env.example                   # 環境変数のテンプレート
├── credentials.json               # Google API認証情報（要配置）
├── token.json                     # 認証トークン（自動生成）
├── chroma_db_openai/              # ベクトルDB（自動生成）
├── Dockerfile                     # Dockerイメージ定義
├── docker-compose.yml             # Docker Compose設定
├── .dockerignore                  # Docker除外ファイル
├── SLACK_SETUP.md                 # Slack App設定ガイド
├── GITHUB_SETUP.md                # GitHub連携ガイド
└── README.md                      # このファイル
```

## 🔧 デバッグ・メンテナンス

### ベクトルDBの内容確認

```bash
python check_vectordb.py
```

ベクトルDBに保存されているドキュメント一覧とメタデータを確認できます。

### ログの確認

Botのログを確認する場合：

```bash
tail -f bot.log
```

### サービスの再起動

```bash
# プロセスを停止
pkill -f slack_bot_hybrid

# 再起動
nohup python -u slack_bot_hybrid.py > bot.log 2>&1 &
```

## 📊 技術スタック

### LLM・埋め込み
- **Google Gemini 2.5 Flash**: 回答生成
- **OpenAI text-embedding-3-large**: テキスト埋め込み

### 検索
- **BM25 (Okapi)**: キーワードベース検索
- **ベクトル検索**: 意味ベース検索
- **ハイブリッドスコアリング**: 両者の統合（重み: 50/50）

### データベース・フレームワーク
- **ChromaDB**: ベクトルデータベース
- **LangChain**: RAGフレームワーク
- **Slack Bolt**: Slack Bot開発

### PDF処理
- **PyMuPDF (fitz)**: PDF解析
- **LangChain TextSplitter**: チャンク分割

## ❓ トラブルシューティング

### PDFが見つからない

- Google DriveのフォルダIDが正しいか確認
- フォルダに閲覧権限があるか確認
- credentials.jsonが正しく配置されているか確認

### APIエラー

- `.env`ファイルの各APIキーが正しいか確認
- APIの使用量制限に達していないか確認
- OpenAI APIの残高を確認

### 認証エラー

- credentials.jsonが正しいか確認
- token.jsonを削除して再認証を試す

### Slack Botが反応しない

1. **Botがオンラインか確認**
   ```bash
   ps aux | grep slack_bot_hybrid
   ```

2. **ログを確認**
   ```bash
   tail -50 bot.log
   ```

3. **イベント購読を確認**
   - Slack App設定で`message.channels`が購読されているか確認
   - Appを再インストール

4. **権限を確認**
   - Botが該当チャネルに招待されているか確認
   - 必要なスコープが付与されているか確認

### スレッド内で追加情報が認識されない

- Botプロセスが起動しているか確認
- `message.channels`イベントが購読されているか確認
- ログで`[handle_message呼び出し]`が表示されるか確認

## 🎨 カスタマイズ

### 検索パラメータの調整

`slack_bot_hybrid.py`で以下を変更:

```python
TOP_K_RESULTS = 5  # 検索結果の上位件数

# ハイブリッド検索の重み
hybrid_retriever = HybridSearchRetriever(
    vectordb=vectordb,
    alpha=0.5  # ベクトル検索の重み（0.0〜1.0）
)
```

### プロンプトのカスタマイズ

`PROMPT_TEMPLATE`や`CLARITY_CHECK_PROMPT`を編集して、回答スタイルや判定基準を調整できます。

### 法律の追加

`LAW_TYPES`と`LAW_SOURCE_MAPPING`にエントリを追加:

```python
LAW_TYPES = {
    # ... 既存 ...
    "new_law": "新しい法律名"
}

LAW_SOURCE_MAPPING = {
    # ... 既存 ...
    "新しい法律名": ["ファイル名1.pdf", "ファイル名2.pdf"]
}
```

ボタンも`create_law_selection_blocks()`に追加してください。

## 📝 ライセンス

MIT

## 🙏 謝辞

このプロジェクトは以下のオープンソースプロジェクトを使用しています：
- LangChain
- ChromaDB
- Slack Bolt for Python
- OpenAI API
- Google Gemini API
