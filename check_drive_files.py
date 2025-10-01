#!/usr/bin/env python3
"""
Google Driveフォルダ内のファイルを確認するスクリプト
"""

import os
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# 環境変数の読み込み
load_dotenv()
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

def authenticate_google_drive():
    """Google Drive APIの認証を行います"""
    creds = None
    
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return build('drive', 'v3', credentials=creds)

def list_files_in_folder(service, folder_id):
    """指定したフォルダ内のファイルをリストアップします"""
    try:
        # フォルダ内のすべてのファイルを検索
        query = f"'{folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query,
            fields="files(id, name, mimeType, size, modifiedTime)",
            orderBy="modifiedTime desc"
        ).execute()
        
        files = results.get('files', [])
        
        return files
    except Exception as e:
        print(f"エラー: {str(e)}")
        return []

def main():
    print("=" * 60)
    print("Google Driveフォルダ内のファイル確認")
    print("=" * 60)
    
    if not GOOGLE_DRIVE_FOLDER_ID:
        print("エラー: .envファイルにGOOGLE_DRIVE_FOLDER_IDを設定してください。")
        return
    
    print(f"\nフォルダID: {GOOGLE_DRIVE_FOLDER_ID}")
    print("\nGoogle Driveに接続中...")
    
    service = authenticate_google_drive()
    print("✓ 認証完了\n")
    
    print("ファイルを取得中...")
    files = list_files_in_folder(service, GOOGLE_DRIVE_FOLDER_ID)
    
    if not files:
        print("\n⚠️  フォルダ内にファイルが見つかりませんでした。")
        print("\n考えられる原因:")
        print("  - フォルダIDが間違っている")
        print("  - フォルダが空")
        print("  - フォルダへのアクセス権限がない")
        return
    
    print(f"\n✓ {len(files)} 個のファイルが見つかりました:\n")
    
    pdf_count = 0
    other_count = 0
    
    for i, file in enumerate(files, 1):
        name = file.get('name', '名前なし')
        mime_type = file.get('mimeType', '不明')
        size = file.get('size', '0')
        modified = file.get('modifiedTime', '不明')
        
        # ファイルサイズを読みやすく変換
        try:
            size_mb = int(size) / (1024 * 1024)
            size_str = f"{size_mb:.2f} MB"
        except:
            size_str = "不明"
        
        # PDFファイルかどうかチェック
        is_pdf = mime_type == 'application/pdf'
        if is_pdf:
            pdf_count += 1
            icon = "📄"
        else:
            other_count += 1
            icon = "📁"
        
        print(f"{icon} [{i}] {name}")
        print(f"    タイプ: {mime_type}")
        print(f"    サイズ: {size_str}")
        print(f"    更新日: {modified[:10]}")
        print()
    
    print("=" * 60)
    print(f"PDFファイル: {pdf_count} 個")
    print(f"その他のファイル: {other_count} 個")
    print("=" * 60)
    
    if pdf_count > 0:
        print("\n✅ PDFファイルが見つかりました！")
        print("   prepare_database.py を実行してベクトルDBを作成できます。")
    else:
        print("\n⚠️  PDFファイルが見つかりませんでした。")
        print("   PDFファイルをアップロードしてください。")

if __name__ == "__main__":
    main()

