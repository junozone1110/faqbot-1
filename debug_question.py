#!/usr/bin/env python3
"""
FAQボット - デバッグ版
チャンクの内容を表示して確認します
"""

import os
import sys
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma

# 設定
CHROMA_DB_DIR = "./chroma_db"
TOP_K_RESULTS = 5

# 環境変数の読み込み
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


def load_vectordb():
    """ベクトルDBを読み込みます"""
    if not os.path.exists(CHROMA_DB_DIR):
        print(f"エラー: ベクトルDB ({CHROMA_DB_DIR}) が見つかりません。")
        return None
    
    embedding_model = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004",
        google_api_key=GOOGLE_API_KEY
    )
    
    vectordb = Chroma(
        persist_directory=CHROMA_DB_DIR,
        embedding_function=embedding_model
    )
    
    return vectordb


def main():
    """メイン処理"""
    if len(sys.argv) < 2:
        print("使い方: python debug_question.py \"質問内容\"")
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    
    print("=" * 80)
    print(f"質問: {query}")
    print("=" * 80)
    
    if not GOOGLE_API_KEY:
        print("エラー: .envファイルにGOOGLE_API_KEYを設定してください。")
        sys.exit(1)
    
    print("\nベクトルDBを読み込み中...")
    vectordb = load_vectordb()
    if vectordb is None:
        sys.exit(1)
    
    print("関連チャンクを検索中...\n")
    results = vectordb.similarity_search_with_score(query, k=TOP_K_RESULTS)
    
    if not results:
        print("関連する情報が見つかりませんでした。")
        sys.exit(0)
    
    for i, (doc, score) in enumerate(results, 1):
        source = doc.metadata.get('source', '不明')
        chunk_id = doc.metadata.get('chunk_id', '不明')
        similarity = 1 - score
        
        print("=" * 80)
        print(f"[チャンク {i}]")
        print(f"出典: {source}")
        print(f"チャンクID: {chunk_id}")
        print(f"類似度: {similarity:.3f}")
        print("-" * 80)
        print(f"内容:\n{doc.page_content}")
        print("=" * 80)
        print()


if __name__ == "__main__":
    main()

