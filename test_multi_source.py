#!/usr/bin/env python3
"""
マルチソース検索のテスト
各ファイルから上位2件ずつ取得
"""

from hybrid_search import HybridSearchRetriever
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
import os
from dotenv import load_dotenv

load_dotenv()

CHROMA_DB_DIR = "./chroma_db_openai"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

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

# ハイブリッド検索の初期化
hybrid_retriever = HybridSearchRetriever(
    vectordb=vectordb,
    alpha=0.5  # BM25とベクトル検索を同じ重みで
)

query = "景品類の定義を教えて"
print(f"検索クエリ: {query}\n")
print("=" * 100)
print("マルチソース検索（各ファイルから上位2件ずつ）:\n")

results = hybrid_retriever.search_multi_source(query, k_per_source=2)

for i, (doc, score) in enumerate(results, 1):
    source = doc.metadata.get('source', '不明')
    bm25_score = doc.metadata.get('bm25_score', 0)
    vector_score = doc.metadata.get('vector_score', 0)
    
    # ファイル名を短縮
    if 'Q&A' in source:
        source_label = "FAQ"
    elif '施行規則' in source:
        source_label = "施行規則"
    elif '不当景品類及び不当表示防止法.pdf' in source:
        source_label = "★法律★"
    else:
        source_label = source
    
    print(f"[{i}] {source_label:10s} | ハイブリッド: {score:.4f} (BM25: {bm25_score:.4f}, ベクトル: {vector_score:.4f})")
    print(f"    内容: {doc.page_content[:150]}...")
    print()

