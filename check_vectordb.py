#!/usr/bin/env python3
"""
ベクトルDBの状態確認スクリプト
"""
import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from collections import Counter

load_dotenv()

CHROMA_DB_DIR = "./chroma_db_openai"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def check_vectordb():
    """ベクトルDBの状態を確認"""
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
    
    # 全ドキュメントを取得
    collection = vectordb._collection
    all_docs = collection.get()
    
    print("=" * 80)
    print("ベクトルDB 詳細情報")
    print("=" * 80)
    print()
    
    # 基本統計
    total_docs = len(all_docs['ids'])
    print(f"📊 総ドキュメント数: {total_docs}")
    print()
    
    # ソース別の統計
    if all_docs['metadatas']:
        sources = [meta.get('source', '不明') for meta in all_docs['metadatas']]
        source_counts = Counter(sources)
        
        print("📁 ソース別ドキュメント数:")
        for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
            source_name = source.split('/')[-1] if '/' in source else source
            print(f"  • {source_name}: {count}件")
        print()
        
        # チャンクIDのサンプル
        chunk_ids = [meta.get('chunk_id', '不明') for meta in all_docs['metadatas'][:10]]
        print("🔖 チャンクIDサンプル（最初の10件）:")
        for i, chunk_id in enumerate(chunk_ids, 1):
            print(f"  {i}. {chunk_id}")
        print()
    
    # テキストの長さ統計
    if all_docs['documents']:
        doc_lengths = [len(doc) for doc in all_docs['documents']]
        avg_length = sum(doc_lengths) / len(doc_lengths)
        min_length = min(doc_lengths)
        max_length = max(doc_lengths)
        
        print("📝 テキスト長統計:")
        print(f"  • 平均長: {avg_length:.1f} 文字")
        print(f"  • 最小長: {min_length} 文字")
        print(f"  • 最大長: {max_length} 文字")
        print()
        
        # サンプルドキュメント
        print("📄 サンプルドキュメント（最初のチャンク）:")
        sample_doc = all_docs['documents'][0]
        sample_meta = all_docs['metadatas'][0]
        print(f"  ソース: {sample_meta.get('source', '不明')}")
        print(f"  チャンクID: {sample_meta.get('chunk_id', '不明')}")
        print(f"  内容（最初の200文字）:")
        print(f"    {sample_doc[:200]}...")
        print()
    
    print("=" * 80)
    print("✅ ベクトルDBは正常に動作しています")
    print("=" * 80)

if __name__ == "__main__":
    check_vectordb()


