# Slack連携セットアップガイド

FAQボットをSlackと連携して、チャネルで質問に回答できるようにします。

## ステップ1: Slack Appの作成

### 1.1 Slack Appを作成

1. [Slack API](https://api.slack.com/apps) にアクセス
2. **「Create New App」** をクリック
3. **「From scratch」** を選択
4. App Name: `FAQ Bot`（任意）
5. Workspace: 使用するワークスペースを選択
6. **「Create App」** をクリック

### 1.2 Bot Tokenのスコープを設定

1. 左メニューから **「OAuth & Permissions」** を選択
2. **「Scopes」** セクションまでスクロール
3. **「Bot Token Scopes」** に以下を追加：
   - `app_mentions:read` - メンションを読む
   - `chat:write` - メッセージを送信
   - `channels:history` - チャネルの履歴を読む
   - `channels:read` - チャネル情報を読む

### 1.3 Event Subscriptionsを有効化

1. 左メニューから **「Event Subscriptions」** を選択
2. **「Enable Events」** をオンに切り替え
3. **「Subscribe to bot events」** に以下を追加：
   - `app_mention` - ボットがメンションされた時
   - `message.channels` - チャネルでメッセージが投稿された時

### 1.4 Socket Modeを有効化（推奨）

Socket Modeを使用すると、公開URLが不要になります。

1. 左メニューから **「Socket Mode」** を選択
2. **「Enable Socket Mode」** をオンに切り替え
3. Token Name: `faq-bot-socket`（任意）
4. **「Generate」** をクリック
5. 表示されたトークン（`xapp-`で始まる）をコピー → **App-Level Token**

### 1.5 トークンの取得

#### Bot Token
1. 左メニューから **「OAuth & Permissions」** を選択
2. **「Install to Workspace」** をクリック
3. **「許可する」** をクリック
4. **「Bot User OAuth Token」**（`xoxb-`で始まる）をコピー

#### App-Level Token
- ステップ1.4で取得済み（`xapp-`で始まる）

---

## ステップ2: 環境変数の設定

`.env`ファイルにSlackトークンを追加：

```bash
# 既存の設定
GOOGLE_DRIVE_FOLDER_ID="18LcNhRWlkp8Cx00caF6b1MAB6GMH3J0U"
GOOGLE_API_KEY="AIzaSyDg2HqkLl92y-J8gW395_hrJXXE__Y0KJY"
OPENAI_API_KEY="sk-proj-..."

# Slack設定（追加）
SLACK_BOT_TOKEN="xoxb-your-bot-token-here"
SLACK_APP_TOKEN="xapp-your-app-token-here"
```

---

## ステップ3: ボットをチャネルに追加

1. Slackで使用するチャネルを開く
2. チャネル名をクリック → **「インテグレーション」** タブ
3. **「アプリを追加する」** をクリック
4. 作成した `FAQ Bot` を選択して追加

---

## ステップ4: ボットの起動

```bash
source venv/bin/activate
python slack_bot.py
```

起動すると以下のように表示されます：
```
⚡️ Bolt app is running!
✓ FAQ Bot が起動しました
チャネルで @FAQ Bot をメンションして質問してください
```

---

## 使い方

### チャネルでの使用方法

1. **メンションして質問**
   ```
   @FAQ Bot 景品類の定義を教えてください
   ```

2. **ダイレクトメッセージ**
   - ボットにDMを送信すると、メンションなしでも応答します

3. **複数の質問**
   - 各質問に対して、参照元を明示した詳細な回答を返します

---

## トラブルシューティング

### エラー: "invalid_auth"
→ `SLACK_BOT_TOKEN`が正しいか確認してください（`xoxb-`で始まる）

### エラー: "not_allowed_token_type"
→ Socket Modeを有効にして、`SLACK_APP_TOKEN`を設定してください（`xapp-`で始まる）

### ボットが応答しない
→ 以下を確認：
1. ボットがチャネルに追加されているか
2. `@FAQ Bot` のようにメンションしているか
3. `slack_bot.py`が起動しているか

### エラー: "channel_not_found"
→ ボットをチャネルに追加してください

---

## セキュリティ上の注意

- `.env`ファイルは絶対にGitにコミットしないでください
- トークンは安全に管理してください
- 本番環境では、環境変数をシステムレベルで設定することを推奨します

