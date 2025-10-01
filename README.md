# FAQボット

Google Drive上のPDFファイルからFAQボットを作成するアプリケーションです。
RAG（Retrieval-Augmented Generation）を使用して、PDFの内容に基づいて質問に回答します。

## 機能

- Google DriveからPDFファイルを自動ダウンロード
- PDFをテキスト化し、検索可能なベクトルDBに保存
- 質問に対して関連情報を検索し、LLMで回答を生成

## セットアップ

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

### 4. 環境変数の設定

`.env.example`をコピーして`.env`ファイルを作成し、必要な情報を入力します。

```bash
cp .env.example .env
```

`.env`ファイルを編集：

```
GOOGLE_DRIVE_FOLDER_ID="あなたのDriveフォルダID"
GOOGLE_API_KEY="あなたのGemini APIキー"
```

**Google DriveフォルダIDの取得方法:**
- Google DriveでフォルダのURLを確認
- `https://drive.google.com/drive/folders/FOLDER_ID` の `FOLDER_ID` 部分

**Gemini APIキーの取得方法:**
- [Google AI Studio](https://makersuite.google.com/app/apikey)でAPIキーを作成

## 使い方

### ステップ1: データベースの準備

Google DriveからPDFをダウンロードし、ベクトルDBを作成します。

```bash
python prepare_database.py
```

初回実行時、ブラウザで認証が求められます。

### ステップ2: ボットに質問

```bash
python ask_bot.py
```

質問を入力すると、PDFの内容に基づいて回答が生成されます。

## ファイル構成

```
09_faq-bot/
├── prepare_database.py    # データベース準備スクリプト
├── ask_bot.py             # 質問応答ボット
├── requirements.txt       # 必要なライブラリ
├── .env                   # 環境変数（要作成）
├── .env.example           # 環境変数のテンプレート
├── credentials.json       # Google API認証情報（要配置）
├── token.json             # 認証トークン（自動生成）
├── chroma_db/             # ベクトルDB（自動生成）
└── README.md              # このファイル
```

## トラブルシューティング

### PDFが見つからない

- Google DriveのフォルダIDが正しいか確認
- フォルダに閲覧権限があるか確認
- credentials.jsonが正しく配置されているか確認

### APIエラー

- .envファイルのGOOGLE_API_KEYが正しいか確認
- APIの使用量制限に達していないか確認

### 認証エラー

- credentials.jsonが正しいか確認
- token.jsonを削除して再認証を試す

## ライセンス

MIT

