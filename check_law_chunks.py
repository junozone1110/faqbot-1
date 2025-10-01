#!/usr/bin/env python3
"""
法律条文のチャンクを確認するスクリプト
"""

import os
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

CHROMA_DB_DIR = "./chroma_db_openai"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    print("エラー: OPENAI_API_KEYが設定されていません")
    exit(1)

# 埋め込みモデルの初期化
embedding_model = OpenAIEmbeddings(
    model="text-embedding-3-large",
    openai_api_key=OPENAI_API_KEY
)

# ベクトルDBの読み込み
vectordb = Chroma(
    persist_directory=CHROMA_DB_DIR,
    embedding_function=embedding_model
)

# 全データを取得
all_data = vectordb.get()

# 法律条文のチャンクだけをフィルタリング
law_chunks = []
for i, (doc, meta) in enumerate(zip(all_data['documents'], all_data['metadatas'])):
    if '不当景品類及び不当表示防止法.pdf' in meta.get('source', ''):
        law_chunks.append((i, doc, meta))

print(f"=" * 80)
print(f"法律条文のチャンク数: {len(law_chunks)}")
print(f"=" * 80)

print("\n最初の5つの法律条文チャンク:\n")

for i, (idx, content, meta) in enumerate(law_chunks[:5]):
    print(f"\n{'=' * 80}")
    print(f"[法律チャンク {i+1}/{len(law_chunks)}]")
    print(f"出典: {meta.get('source')}")
    print(f"チャンクID: {meta.get('chunk_id')}")
    print(f"-" * 80)
    print(content)
    print(f"{'=' * 80}\n")

# 「定義」を含むチャンクを検索
print(f"\n{'#' * 80}")
print("「定義」を含む法律チャンク:")
print(f"{'#' * 80}\n")

definition_chunks = [(i, doc, meta) for i, doc, meta in law_chunks if '定義' in doc]
print(f"「定義」を含むチャンク数: {len(definition_chunks)}\n")

for i, (idx, content, meta) in enumerate(definition_chunks):
    print(f"\n{'=' * 80}")
    print(f"[定義チャンク {i+1}/{len(definition_chunks)}]")
    print(f"チャンクID: {meta.get('chunk_id')}")
    print(f"-" * 80)
    print(content)
    print(f"{'=' * 80}\n")

# 景品類の定義に関する質問でテスト検索
print(f"\n{'#' * 80}")
print("テスト検索: 「景品類の定義を教えて」")
print(f"{'#' * 80}\n")

results = vectordb.similarity_search_with_score("景品類の定義を教えて", k=10)

for i, (doc, score) in enumerate(results, 1):
    source = doc.metadata.get('source', '不明')
    chunk_id = doc.metadata.get('chunk_id', '不明')
    content = doc.page_content
    similarity = -score  # 距離をスコアに変換
    
    print(f"\n[{i}] 類似度スコア: {score:.4f} (類似度: {similarity:.4f})")
    print(f"出典: {source}")
    print(f"チャンクID: {chunk_id}")
    print(f"-" * 80)
    print(content[:300] + "...")
    print()

