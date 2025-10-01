#!/usr/bin/env python3
"""
FAQ Bot with Hybrid Search (OpenAI Embeddings + BM25)
ハイブリッド検索を使用したFAQ Botのコマンドライン版
"""

import os
import argparse
from dotenv import load_dotenv

from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from hybrid_search import HybridSearchRetriever

# 環境変数の読み込み
load_dotenv()

# 定数
CHROMA_DB_DIR = "./chroma_db_openai"
TOP_K_RESULTS = 5  # 検索結果の上位件数
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# プロンプトテンプレート
PROMPT_TEMPLATE = """
あなたは景品表示法やFAQに関する質問に回答する親切なアシスタントです。
以下のコンテキスト情報を参考にして、質問に日本語で分かりやすく回答してください。

**重要な指示**:
1. 回答する際は、必ず情報の出典を明示してください
2. 各文や段落の最後に、その情報がどの参照から来ているかを（[参照1]）のように記載してください
3. 複数の参照から情報を得た場合は、（[参照1, 2]）のように記載してください
4. コンテキスト情報に直接的な回答がない場合でも、関連する情報があれば、出典を明示した上で回答を提供してください
5. 全く関連する情報がない場合は、「提供された情報には、この質問に対する回答が含まれていません」と答えてください
6. 法律条文、施行規則、FAQ それぞれの情報を区別して活用してください

# コンテキスト情報
{context}

# 質問
{question}

# 回答（必ず参照元を明示してください）
"""


def load_vectordb_with_hybrid_search():
    """ベクトルDBを読み込み、ハイブリッド検索retrieverを作成"""
    if not os.path.exists(CHROMA_DB_DIR):
        raise FileNotFoundError(
            f"ベクトルDB ({CHROMA_DB_DIR}) が見つかりません。\n"
            f"まず prepare_database_openai.py を実行してベクトルDBを作成してください。"
        )
    
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
    
    # ハイブリッド検索retrieverの作成
    hybrid_retriever = HybridSearchRetriever(
        vectordb=vectordb,
        alpha=0.5  # BM25とベクトル検索を同じ重みで
    )
    
    return hybrid_retriever


def format_docs(docs):
    """ドキュメントをフォーマットして、参照番号を付与"""
    context_parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get('source', '不明')
        chunk_id = doc.metadata.get('chunk_id', '不明')
        
        # ファイル名を短縮
        if 'Q&A' in source:
            source_type = "FAQ"
        elif '施行規則' in source:
            source_type = "施行規則"
        elif '不当景品類及び不当表示防止法.pdf' in source:
            source_type = "景表法"
        else:
            source_type = source
        
        context_parts.append(
            f"[参照{i}] (出典: {source_type}, {source}, ID: {chunk_id})\n{doc.page_content}\n"
        )
    
    return "\n".join(context_parts)


def ask_question(query: str, hybrid_retriever):
    """質問に対して回答を生成"""
    # ハイブリッド検索で上位TOP_K_RESULTS件を取得
    docs_and_scores = hybrid_retriever.search(query, k=TOP_K_RESULTS)
    docs = [doc for doc, score in docs_and_scores]
    
    # LLMの初期化
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=GOOGLE_API_KEY,
        temperature=0.2,
    )
    
    # プロンプトの作成
    prompt = PromptTemplate.from_template(PROMPT_TEMPLATE)
    
    # RAGチェーンの構築
    rag_chain = (
        {
            "context": lambda x: format_docs(docs),
            "question": RunnablePassthrough()
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    
    # 回答の生成
    answer = rag_chain.invoke(query)
    
    # 参照元情報の整形
    references = []
    for i, (doc, score) in enumerate(docs_and_scores, 1):
        source = doc.metadata.get('source', '不明')
        chunk_id = doc.metadata.get('chunk_id', '不明')
        
        # ファイル名を短縮
        if 'Q&A' in source:
            source_label = "FAQ"
        elif '施行規則' in source:
            source_label = "施行規則"
        elif '不当景品類及び不当表示防止法.pdf' in source:
            source_label = "★景表法★"
        else:
            source_label = source
        
        hybrid_score = doc.metadata.get('hybrid_score', 0)
        bm25_score = doc.metadata.get('bm25_score', 0)
        vector_score = doc.metadata.get('vector_score', 0)
        
        references.append(
            f"[{i}] {source_label} - {source}\n"
            f"    (ハイブリッドスコア: {hybrid_score:.4f}, "
            f"BM25: {bm25_score:.4f}, ベクトル: {vector_score:.4f})\n"
            f"    チャンクID: {chunk_id}"
        )
    
    return answer, references


def main():
    parser = argparse.ArgumentParser(description="FAQ Bot with Hybrid Search")
    parser.add_argument("question", nargs="?", help="質問内容")
    parser.add_argument("--top-k", type=int, default=TOP_K_RESULTS, 
                        help=f"検索結果の上位件数（デフォルト: {TOP_K_RESULTS}）")
    args = parser.parse_args()
    
    # 環境変数のチェック
    if not OPENAI_API_KEY or not GOOGLE_API_KEY:
        print("エラー: OPENAI_API_KEY と GOOGLE_API_KEY を .env ファイルに設定してください")
        return
    
    print("=" * 60)
    print("FAQボット (ハイブリッド検索版)")
    print("=" * 60)
    print()
    
    # 質問の取得
    if args.question:
        query = args.question
    else:
        query = input("質問を入力してください: ")
    
    print(f"\n質問: {query}\n")
    
    try:
        print("ベクトルDBを読み込み中...")
        hybrid_retriever = load_vectordb_with_hybrid_search()
        
        print("関連情報を検索中（ハイブリッド検索使用）...")
        print(f"  - 上位{TOP_K_RESULTS}件を取得")
        print("回答を生成中...\n")
        
        answer, references = ask_question(query, hybrid_retriever)
        
        print("=" * 60)
        print("回答:")
        print(answer)
        print("\n" + "=" * 60)
        print("参照元:")
        for ref in references:
            print(f"  {ref}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nエラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

