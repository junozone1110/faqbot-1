# FAQボット - OpenAI Embeddings版

より高精度な埋め込みモデル（OpenAI text-embedding-3-large）を使用したバージョンです。

## OpenAI Embeddingsの利点

- **高精度**: Geminiよりも日本語の埋め込み精度が高い
- **安定性**: 検索結果の一貫性が向上
- **FAQに最適**: Q&A形式のドキュメントの検索に優れている

## セットアップ

### 1. OpenAI APIキーの取得

1. [OpenAI Platform](https://platform.openai.com/api-keys) にアクセス
2. サインイン（アカウントがない場合は作成）
3. **「Create new secret key」** をクリック
4. 生成されたAPIキーをコピー（例: `sk-...`）

### 2. 環境変数の設定

`.env`ファイルにOpenAI APIキーを追加：

```bash
# 既存の設定
GOOGLE_DRIVE_FOLDER_ID="18LcNhRWlkp8Cx00caF6b1MAB6GMH3J0U"
GOOGLE_API_KEY="AIzaSyDg2HqkLl92y-J8gW395_hrJXXE__Y0KJY"

# 追加: OpenAI API Key
OPENAI_API_KEY="sk-your-openai-api-key-here"
```

### 3. OpenAIライブラリのインストール

```bash
source venv/bin/activate
pip install openai langchain-openai
```

## 使い方

### ステップ1: データベースの準備（OpenAI版）

```bash
python prepare_database_openai.py
```

このコマンドは：
- Google DriveからPDFをダウンロード
- テキストを抽出してチャンクに分割
- **OpenAI text-embedding-3-large** でベクトル化
- `chroma_db_openai/` に保存

### ステップ2: ボットに質問（OpenAI版）

```bash
python ask_question_openai.py "景品類の定義を教えてください"
```

## 比較：Gemini vs OpenAI Embeddings

### Gemini版（従来）
```bash
python prepare_database.py      # Gemini埋め込み
python ask_question.py "質問"   # chroma_db/ を使用
```

### OpenAI版（高精度）
```bash
python prepare_database_openai.py    # OpenAI埋め込み
python ask_question_openai.py "質問" # chroma_db_openai/ を使用
```

## コスト

### OpenAI text-embedding-3-large
- 入力: $0.13 / 1M トークン
- 目安: 100ページのPDF = 約 $0.02〜0.05

### Gemini text-embedding-004
- 無料（制限あり）

## トラブルシューティング

### エラー: "OPENAI_API_KEY が見つかりません"

→ `.env`ファイルにOPENAI_API_KEYを設定してください

```bash
echo 'OPENAI_API_KEY="sk-your-api-key"' >> .env
```

### エラー: "You exceeded your current quota"

→ OpenAIアカウントの使用量制限に達しています
- [Usage Dashboard](https://platform.openai.com/usage) で確認
- 必要に応じてクレジットを追加

## 推奨

**FAQボットには OpenAI版の使用を推奨します**：
- ✅ 検索精度が大幅に向上
- ✅ Q&A形式のドキュメントに最適
- ✅ 日本語の理解が優れている

コストが気になる場合は、Gemini版も利用可能です。

