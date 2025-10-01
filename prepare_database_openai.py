#!/usr/bin/env python3
"""
PDF読み込みとベクトルDB保存スクリプト (OpenAI Embeddings版)
Google DriveからPDFファイルをダウンロードし、チャンク化してChromaDBに保存します。
OpenAIの高精度な埋め込みモデルを使用します。
"""

import os
import shutil
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import fitz  # PyMuPDF

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

# 設定
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
TEMP_PDF_DIR = Path("./temp_pdf")
CHROMA_DB_DIR = "./chroma_db_openai"

# 環境変数の読み込み
load_dotenv()
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def authenticate_google_drive():
    """Google Drive APIの認証を行います"""
    creds = None
    
    # token.jsonがあれば読み込む
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # 認証情報がない、または無効な場合
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # 認証情報を保存
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return build('drive', 'v3', credentials=creds)


def get_all_pdfs_recursive(service, folder_id: str, path_prefix: str = ""):
    """指定したGoogle Driveフォルダから再帰的にすべてのPDFを取得します"""
    all_pdfs = []
    
    # フォルダ内のすべてのファイルとフォルダを取得
    query = f"'{folder_id}' in parents and trashed=false"
    results = service.files().list(
        q=query,
        fields="files(id, name, mimeType)"
    ).execute()
    
    items = results.get('files', [])
    
    for item in items:
        item_name = item['name']
        item_id = item['id']
        mime_type = item['mimeType']
        
        # PDFファイルの場合
        if mime_type == 'application/pdf':
            full_path = f"{path_prefix}/{item_name}" if path_prefix else item_name
            all_pdfs.append({
                'id': item_id,
                'name': item_name,
                'path': full_path
            })
        
        # フォルダの場合、再帰的に探索
        elif mime_type == 'application/vnd.google-apps.folder':
            folder_path = f"{path_prefix}/{item_name}" if path_prefix else item_name
            print(f"📁 フォルダを探索中: {folder_path}")
            sub_pdfs = get_all_pdfs_recursive(service, item_id, folder_path)
            all_pdfs.extend(sub_pdfs)
    
    return all_pdfs


def download_pdfs_from_drive(service, folder_id: str, download_dir: Path):
    """指定したGoogle DriveフォルダからすべてのPDFをダウンロードします（再帰的）"""
    # ダウンロード先ディレクトリを作成
    download_dir.mkdir(exist_ok=True)
    
    # 再帰的にPDFを取得
    print("フォルダ構造を探索中...")
    pdf_files = get_all_pdfs_recursive(service, folder_id)
    
    if not pdf_files:
        print("PDFファイルが見つかりませんでした。")
        return []
    
    print(f"\n合計{len(pdf_files)}個のPDFファイルが見つかりました。")
    
    downloaded_files = []
    for pdf_info in pdf_files:
        file_id = pdf_info['id']
        file_name = pdf_info['name']
        full_path_in_drive = pdf_info['path']
        local_file_path = download_dir / file_name
        
        print(f"ダウンロード中: {full_path_in_drive}")
        
        request = service.files().get_media(fileId=file_id)
        with open(local_file_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    print(f"  進捗: {int(status.progress() * 100)}%")
        
        downloaded_files.append(local_file_path)
    
    return downloaded_files


def extract_text_from_pdf(pdf_path: Path) -> str:
    """PDFファイルからテキストを抽出します"""
    print(f"テキスト抽出中: {pdf_path.name}")
    
    doc = fitz.open(pdf_path)
    text = ""
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text += page.get_text()
    
    doc.close()
    return text


def create_chunks(texts: List[dict], chunk_size: int = 1500, chunk_overlap: int = 300) -> List[dict]:
    """テキストを適切なサイズのチャンクに分割します"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    
    all_chunks = []
    
    for text_dict in texts:
        chunks = text_splitter.split_text(text_dict['text'])
        for i, chunk in enumerate(chunks):
            all_chunks.append({
                'text': chunk,
                'source': text_dict['source'],
                'chunk_id': f"{text_dict['source']}_chunk_{i}"
            })
    
    return all_chunks


def save_to_chroma(chunks: List[dict], embedding_model):
    """チャンクをベクトル化してChromaDBに保存します（バッチ処理）"""
    total_chunks = len(chunks)
    print(f"\n使用モデル: {embedding_model.model} (高精度)")
    
    # 既存のDBがあれば削除
    if os.path.exists(CHROMA_DB_DIR):
        shutil.rmtree(CHROMA_DB_DIR)
    
    # バッチサイズ（OpenAIのトークン制限に対応）
    BATCH_SIZE = 100  # 100チャンクずつ処理
    
    print(f"\n{total_chunks}個のチャンクを{BATCH_SIZE}個ずつバッチ処理で保存中...")
    
    vectordb = None
    for i in range(0, total_chunks, BATCH_SIZE):
        batch = chunks[i:i+BATCH_SIZE]
        batch_texts = [chunk['text'] for chunk in batch]
        batch_metadatas = [{'source': chunk['source'], 'chunk_id': chunk['chunk_id']} for chunk in batch]
        
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (total_chunks + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  バッチ {batch_num}/{total_batches} ({len(batch)}チャンク) を処理中...")
        
        if vectordb is None:
            # 最初のバッチでDBを作成
            vectordb = Chroma.from_texts(
                texts=batch_texts,
                embedding=embedding_model,
                metadatas=batch_metadatas,
                persist_directory=CHROMA_DB_DIR
            )
        else:
            # 2回目以降は既存のDBに追加
            vectordb.add_texts(
                texts=batch_texts,
                metadatas=batch_metadatas
            )
    
    print(f"\n✓ ベクトルDBの保存完了: {CHROMA_DB_DIR}")
    print(f"  合計チャンク数: {total_chunks}")
    return vectordb


def main():
    """メイン処理"""
    print("=== FAQボット用データベース準備スクリプト (OpenAI Embeddings版) ===\n")
    
    # 環境変数のチェック
    if not GOOGLE_DRIVE_FOLDER_ID or not OPENAI_API_KEY:
        print("エラー: .envファイルにGOOGLE_DRIVE_FOLDER_IDとOPENAI_API_KEYを設定してください。")
        print("\nOpenAI APIキーの取得方法:")
        print("1. https://platform.openai.com/api-keys にアクセス")
        print("2. 'Create new secret key' をクリック")
        print("3. 生成されたAPIキーを.envファイルのOPENAI_API_KEYに設定")
        return
    
    # Step 1: Google Drive認証
    print("Step 1: Google Driveに接続中...")
    service = authenticate_google_drive()
    print("認証完了\n")
    
    # Step 2: PDFダウンロード
    print("Step 2: PDFファイルをダウンロード中...")
    pdf_files = download_pdfs_from_drive(service, GOOGLE_DRIVE_FOLDER_ID, TEMP_PDF_DIR)
    print(f"{len(pdf_files)}個のPDFをダウンロード完了\n")
    
    if not pdf_files:
        print("PDFファイルがないため、処理を終了します。")
        return
    
    # Step 3: テキスト抽出
    print("Step 3: PDFからテキストを抽出中...")
    texts = []
    for pdf_path in pdf_files:
        text = extract_text_from_pdf(pdf_path)
        texts.append({
            'text': text,
            'source': pdf_path.name
        })
    print("テキスト抽出完了\n")
    
    # Step 4: チャンク化
    print("Step 4: テキストをチャンクに分割中...")
    chunks = create_chunks(texts)
    print(f"{len(chunks)}個のチャンクを作成\n")
    
    # Step 5: ベクトル化とChromaDBへの保存
    print("Step 5: OpenAI Embeddingsでベクトル化してChromaDBに保存中...")
    print("使用モデル: text-embedding-3-large (高精度)")
    embedding_model = OpenAIEmbeddings(
        model="text-embedding-3-large",
        openai_api_key=OPENAI_API_KEY
    )
    save_to_chroma(chunks, embedding_model)
    
    # 一時ファイルのクリーンアップ
    print("\n一時ファイルをクリーンアップ中...")
    if TEMP_PDF_DIR.exists():
        shutil.rmtree(TEMP_PDF_DIR)
    
    print("\n=== 処理完了 ===")
    print("OpenAI Embeddingsを使用したベクトルDBの準備が完了しました。")
    print("次は ask_bot_openai.py を実行して質問に回答させることができます。")


if __name__ == "__main__":
    main()

