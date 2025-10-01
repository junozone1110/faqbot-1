#!/usr/bin/env python3
"""
ベクトルDBの中身を確認するスクリプト
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma

CHROMA_DB_DIR = "./chroma_db"

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("エラー: .envファイルにGOOGLE_API_KEYを設定してください。")
    exit(1)

embedding_model = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004",
    google_api_key=GOOGLE_API_KEY
)

vectordb = Chroma(
    persist_directory=CHROMA_DB_DIR,
    embedding_function=embedding_model
)

# 全チャンクを取得
all_docs = vectordb.get()

print(f"総チャンク数: {len(all_docs['ids'])}\n")

# ファイル別のチャンク数を集計
file_chunks = {}
for metadata in all_docs['metadatas']:
    source = metadata.get('source', '不明')
    if source not in file_chunks:
        file_chunks[source] = 0
    file_chunks[source] += 1

print("ファイル別のチャンク数:")
for source, count in sorted(file_chunks.items()):
    print(f"  {source}: {count}個")

print("\n最初の3チャンクの内容:")
for i in range(min(3, len(all_docs['ids']))):
    print(f"\n{'='*80}")
    print(f"[チャンク {i+1}]")
    print(f"出典: {all_docs['metadatas'][i].get('source', '不明')}")
    print(f"チャンクID: {all_docs['metadatas'][i].get('chunk_id', '不明')}")
    print(f"-"*80)
    print(f"{all_docs['documents'][i][:500]}...")
    print(f"{'='*80}")

