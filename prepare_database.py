#!/usr/bin/env python3
"""
PDF読み込みとベクトルDB保存スクリプト
Google DriveからPDFファイルをダウンロードし、チャンク化してChromaDBに保存します。
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
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma

# 設定
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
TEMP_PDF_DIR = Path("./temp_pdf")
CHROMA_DB_DIR = "./chroma_db"

# 環境変数の読み込み
load_dotenv()
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


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


def download_pdfs_from_drive(service, folder_id: str, download_dir: Path):
    """指定したGoogle DriveフォルダからすべてのPDFをダウンロードします"""
    # ダウンロード先ディレクトリを作成
    download_dir.mkdir(exist_ok=True)
    
    # フォルダ内のPDFファイルを検索
    query = f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false"
    results = service.files().list(
        q=query,
        fields="files(id, name)"
    ).execute()
    
    files = results.get('files', [])
    
    if not files:
        print("PDFファイルが見つかりませんでした。")
        return []
    
    print(f"{len(files)}個のPDFファイルが見つかりました。")
    
    downloaded_files = []
    for file in files:
        file_id = file['id']
        file_name = file['name']
        file_path = download_dir / file_name
        
        print(f"ダウンロード中: {file_name}")
        
        request = service.files().get_media(fileId=file_id)
        with open(file_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    print(f"  進捗: {int(status.progress() * 100)}%")
        
        downloaded_files.append(file_path)
    
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


def create_chunks(texts: List[dict], chunk_size: int = 2000, chunk_overlap: int = 400) -> List[dict]:
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
    """チャンクをベクトル化してChromaDBに保存します"""
    print(f"\n{len(chunks)}個のチャンクをベクトルDBに保存中...")
    
    # 既存のDBがあれば削除
    if os.path.exists(CHROMA_DB_DIR):
        shutil.rmtree(CHROMA_DB_DIR)
    
    # テキストとメタデータを分離
    texts = [chunk['text'] for chunk in chunks]
    metadatas = [{'source': chunk['source'], 'chunk_id': chunk['chunk_id']} for chunk in chunks]
    
    # ChromaDBに保存
    vectordb = Chroma.from_texts(
        texts=texts,
        embedding=embedding_model,
        metadatas=metadatas,
        persist_directory=CHROMA_DB_DIR
    )
    
    print(f"ベクトルDBの保存完了: {CHROMA_DB_DIR}")
    return vectordb


def main():
    """メイン処理"""
    print("=== FAQボット用データベース準備スクリプト ===\n")
    
    # 環境変数のチェック
    if not GOOGLE_DRIVE_FOLDER_ID or not GOOGLE_API_KEY:
        print("エラー: .envファイルにGOOGLE_DRIVE_FOLDER_IDとGOOGLE_API_KEYを設定してください。")
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
    print("Step 5: ベクトル化してChromaDBに保存中...")
    embedding_model = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004",
        google_api_key=GOOGLE_API_KEY
    )
    save_to_chroma(chunks, embedding_model)
    
    # 一時ファイルのクリーンアップ
    print("\n一時ファイルをクリーンアップ中...")
    if TEMP_PDF_DIR.exists():
        shutil.rmtree(TEMP_PDF_DIR)
    
    print("\n=== 処理完了 ===")
    print("ベクトルDBの準備が完了しました。")
    print("次は ask_bot.py を実行して質問に回答させることができます。")


if __name__ == "__main__":
    main()

