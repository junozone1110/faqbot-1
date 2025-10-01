# GitHubへのSSHキー登録とコードプッシュ手順

## ステップ1: GitHubにSSHキーを登録

### 1-1. 公開鍵をコピー

以下のSSH公開鍵をコピーしてください（FAQ Bot専用に新規作成）：

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHwHt8Lx35NcPguCCnG3NGaopwzjxfTVlhry6eq1kxsf faqbot-1@github
```

### 1-2. GitHubに登録

1. [GitHub Settings - SSH Keys](https://github.com/settings/keys) にアクセス
2. **「New SSH key」** をクリック
3. **Title**: `FAQ Bot MacBook` （任意の名前）
4. **Key type**: `Authentication Key`
5. **Key**: 上記の公開鍵を貼り付け
6. **「Add SSH key」** をクリック

### 1-3. 接続テスト

ターミナルで以下を実行して接続を確認：

```bash
ssh -T git@github.com-faqbot
```

成功すると以下のようなメッセージが表示されます：
```
Hi junozone1110! You've successfully authenticated, but GitHub does not provide shell access.
```

**注意**: `git@github.com-faqbot` は `~/.ssh/config` で設定したHost名です。これにより、FAQ Bot専用のSSHキーが使用されます。

---

## ステップ2: Gitリポジトリの初期化とプッシュ

SSHキーの登録が完了したら、以下のコマンドを実行してください：

### 2-1. Gitリポジトリの初期化

```bash
cd /Users/zone/Documents/work/Cursor/09_faq-bot

# Gitリポジトリを初期化（まだの場合）
git init

# ユーザー情報の設定（必要に応じて）
git config user.name "junozone1110"
git config user.email "junozone@gmail.com"
```

### 2-2. リモートリポジトリの設定

```bash
# SSHのURLでリモートリポジトリを追加（専用のSSHキーを使用）
git remote add origin git@github.com-faqbot:junozone1110/faqbot-1.git

# または既に追加済みの場合は変更
git remote set-url origin git@github.com-faqbot:junozone1110/faqbot-1.git
```

### 2-3. ファイルをステージング

```bash
# 全ファイルを追加（.gitignoreで除外されるファイルは自動的にスキップされます）
git add .

# ステージングされたファイルを確認
git status
```

### 2-4. コミットとプッシュ

```bash
# コミット
git commit -m "Initial commit: FAQ Bot with Slack integration"

# メインブランチの名前を確認・変更
git branch -M main

# GitHubにプッシュ
git push -u origin main
```

---

## ステップ3: .gitignoreの確認

以下のファイルが`.gitignore`に含まれているか確認してください：

- ✅ `.env` - 環境変数（APIキー、トークン）
- ✅ `credentials.json` - Google OAuth認証情報
- ✅ `token.json` - Google認証トークン
- ✅ `venv/` - Python仮想環境
- ✅ `chroma_db/`, `chroma_db_openai/` - ベクトルデータベース
- ✅ `temp_pdf/` - 一時PDFファイル
- ✅ `__pycache__/`, `*.pyc` - Pythonキャッシュ

---

## トラブルシューティング

### エラー: Permission denied (publickey)

→ SSHキーがGitHubに登録されていません。ステップ1を完了してください。

### エラー: remote: Repository not found

→ リポジトリ名が間違っているか、アクセス権限がありません。

### エラー: failed to push some refs

→ リモートに既にコミットがある場合、まずプルしてください：
```bash
git pull origin main --rebase
git push -u origin main
```

---

## 次のステップ

プッシュが完了したら、以下も検討してください：

1. **README.mdの充実** - プロジェクトの説明を追加
2. **GitHub Actionsの設定** - CI/CDパイプライン
3. **Issues/Projects** - タスク管理
4. **Releases** - バージョン管理

---

完了したら、ターミナルに戻って「SSHキーの登録が完了しました」と伝えてください。

