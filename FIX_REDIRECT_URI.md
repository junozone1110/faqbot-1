# redirect_uri_mismatch エラーの修正方法

## エラーの原因
OAuth 2.0認証時に、リダイレクトURIが一致していません。

## 修正手順

### 手順1: Google Cloud Consoleにアクセス
1. [Google Cloud Console](https://console.cloud.google.com/) を開く
2. プロジェクトを選択

### 手順2: OAuth認証情報を編集
1. 左側メニューから「APIとサービス」→「認証情報」を選択
2. 作成済みの「OAuth 2.0 クライアント ID」をクリック

### 手順3: リダイレクトURIを追加
「承認済みのリダイレクト URI」セクションに以下のURIを**すべて**追加してください：

```
http://localhost:8080/
http://localhost:8081/
http://localhost:8082/
http://localhost:8083/
http://localhost:8084/
http://localhost:8085/
http://localhost/
http://127.0.0.1:8080/
http://127.0.0.1:8081/
http://127.0.0.1:8082/
http://127.0.0.1:8083/
http://127.0.0.1:8084/
http://127.0.0.1:8085/
http://127.0.0.1/
```

### 手順4: 保存
「保存」ボタンをクリック

### 手順5: 再実行
設定を保存したら、以下のコマンドで再度実行してください：

```bash
# 既存のtoken.jsonを削除（重要！）
rm -f token.json

# 再度実行
source venv/bin/activate
python check_drive_files.py
```

---

## 別の方法: 新しい認証情報を作成

上記の方法でうまくいかない場合は、新しい認証情報を作成してください：

### 手順1: Google Cloud Consoleで新規作成
1. 「認証情報」→「認証情報を作成」→「OAuth クライアント ID」
2. アプリケーションの種類：**デスクトップアプリ**
3. 名前：任意（例: FAQ Bot Desktop App）
4. 「作成」をクリック

### 手順2: JSONをダウンロード
1. 「JSONをダウンロード」をクリック
2. ダウンロードしたファイルを `credentials.json` にリネーム
3. プロジェクトフォルダに配置（既存のファイルを上書き）

### 手順3: 再実行
```bash
# 既存のtoken.jsonを削除
rm -f token.json

# 再度実行
source venv/bin/activate
python check_drive_files.py
```

---

## トラブルシューティング

### それでもエラーが出る場合
エラーメッセージに表示されている「期待されるリダイレクトURI」を確認し、
その正確なURIをGoogle Cloud Consoleの「承認済みのリダイレクト URI」に追加してください。

例：
```
エラー: redirect_uri_mismatch
期待されるURI: http://localhost:34567/
```

この場合、`http://localhost:34567/` を追加します。

