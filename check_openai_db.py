#!/usr/bin/env python3
"""OpenAI版ベクトルDBの内容を確認"""

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
import os
from dotenv import load_dotenv
from collections import Counter

load_dotenv()

CHROMA_DB_DIR = "./chroma_db_openai"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

embedding_model = OpenAIEmbeddings(
    model="text-embedding-3-large",
    openai_api_key=OPENAI_API_KEY
)

vectordb = Chroma(
    persist_directory=CHROMA_DB_DIR,
    embedding_function=embedding_model
)

all_data = vectordb.get()
print(f"総チャンク数: {len(all_data['documents'])}\n")

# ファイル別の集計
sources = [meta.get('source', '不明') for meta in all_data['metadatas']]
source_counts = Counter(sources)

print("ファイル別のチャンク数:")
for source, count in sorted(source_counts.items()):
    print(f"  {source}: {count}個")

# 法律条文を含むチャンクを表示
print("\n各ファイルの最初のチャンク:\n")

for source in sorted(source_counts.keys()):
    chunks = [(doc, meta) for doc, meta in zip(all_data['documents'], all_data['metadatas']) 
              if meta.get('source') == source]
    
    if chunks:
        doc, meta = chunks[0]
        print(f"=" * 80)
        print(f"ファイル名: {source}")
        print(f"チャンク数: {len(chunks)}")
        print("-" * 80)
        print(doc[:300])
        print("...")
        print()

