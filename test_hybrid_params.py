#!/usr/bin/env python3
"""
ハイブリッド検索のパラメータをテスト
異なるalphaの値で検索結果を比較
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

query = "景品類の定義を教えて"
print(f"検索クエリ: {query}")
print("=" * 100)

# 異なるalphaの値でテスト
alphas = [0.3, 0.4, 0.5, 0.6, 0.7]

for alpha in alphas:
    print(f"\n\n{'#' * 100}")
    print(f"Alpha = {alpha:.1f} (ベクトル検索: {alpha:.1f}, BM25: {1-alpha:.1f})")
    print(f"{'#' * 100}\n")
    
    hybrid_retriever = HybridSearchRetriever(
        vectordb=vectordb,
        alpha=alpha
    )
    
    results = hybrid_retriever.search_with_score_details(query, k=5)
    
    for i, result in enumerate(results, 1):
        source = result['source']
        # ファイル名を短縮
        if 'Q&A' in source:
            source_label = "FAQ"
        elif '施行規則' in source:
            source_label = "施行規則"
        elif '不当景品類及び不当表示防止法.pdf' in source:
            source_label = "★法律★"
        else:
            source_label = source
        
        print(f"[{i}] {source_label:10s} | ハイブリッド: {result['hybrid_score']:.4f} "
              f"(BM25: {result['bm25_score']:.4f}, ベクトル: {result['vector_score']:.4f})")
        print(f"    {result['content'][:100]}")
        print()

