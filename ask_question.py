#!/usr/bin/env python3
"""
FAQボット - 単発質問スクリプト
コマンドライン引数で質問を受け取り、回答を生成します。

使い方:
  python ask_question.py "質問内容"
"""

import os
import sys
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import Chroma

# 設定
CHROMA_DB_DIR = "./chroma_db"
TOP_K_RESULTS = 5  # 検索する関連チャンクの数

# 環境変数の読み込み
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# プロンプトテンプレート
PROMPT_TEMPLATE = """
あなたは景品表示法やFAQに関する質問に回答する親切なアシスタントです。
以下のコンテキスト情報を参考にして、質問に日本語で分かりやすく回答してください。

コンテキスト情報に直接的な回答がない場合でも、関連する情報があれば、
それを基に可能な範囲で回答を提供してください。
ただし、全く関連する情報がない場合は、「提供された情報には、この質問に対する回答が含まれていません」と答えてください。

# コンテキスト情報
{context}

# 質問
{question}

# 回答
"""


def load_vectordb():
    """ベクトルDBを読み込みます"""
    if not os.path.exists(CHROMA_DB_DIR):
        print(f"エラー: ベクトルDB ({CHROMA_DB_DIR}) が見つかりません。")
        print("先に prepare_database.py を実行してデータベースを作成してください。")
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


def search_relevant_chunks(vectordb, query: str, k: int = TOP_K_RESULTS):
    """質問に関連するチャンクを検索します"""
    results = vectordb.similarity_search_with_score(query, k=k)
    return results


def generate_answer(query: str, relevant_chunks):
    """LLMを使って回答を生成します"""
    # コンテキストの作成
    context_parts = []
    for i, (doc, score) in enumerate(relevant_chunks, 1):
        source = doc.metadata.get('source', '不明')
        chunk_id = doc.metadata.get('chunk_id', '不明')
        context_parts.append(f"[参照{i}] (出典: {source}, ID: {chunk_id})\n{doc.page_content}\n")
    
    context = "\n".join(context_parts)
    
    # プロンプトの組み立て
    prompt = PROMPT_TEMPLATE.format(context=context, question=query)
    
    # LLMの初期化と回答生成
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=GOOGLE_API_KEY,
        temperature=0.2,  # 回答の一貫性を高めるため低めに設定
    )
    
    response = llm.invoke(prompt)
    
    return response.content, relevant_chunks


def main():
    """メイン処理"""
    # コマンドライン引数のチェック
    if len(sys.argv) < 2:
        print("使い方: python ask_question.py \"質問内容\"")
        print("\n例:")
        print('  python ask_question.py "景品表示法とは何ですか？"')
        print('  python ask_question.py "懸賞の景品の上限金額はいくらですか？"')
        sys.exit(1)
    
    # 質問を取得
    query = " ".join(sys.argv[1:])
    
    print("=" * 60)
    print("FAQボット")
    print("=" * 60)
    print(f"\n質問: {query}\n")
    
    # 環境変数のチェック
    if not GOOGLE_API_KEY:
        print("エラー: .envファイルにGOOGLE_API_KEYを設定してください。")
        sys.exit(1)
    
    # ベクトルDBの読み込み
    print("ベクトルDBを読み込み中...")
    vectordb = load_vectordb()
    if vectordb is None:
        sys.exit(1)
    
    print("関連情報を検索中...")
    
    # 関連チャンクの検索
    relevant_chunks = search_relevant_chunks(vectordb, query)
    
    if not relevant_chunks:
        print("\n回答: 関連する情報が見つかりませんでした。")
        sys.exit(0)
    
    print("回答を生成中...\n")
    
    # 回答の生成
    answer, chunks = generate_answer(query, relevant_chunks)
    
    # 結果の表示
    print("=" * 60)
    print("回答:")
    print(answer)
    print("\n" + "=" * 60)
    print("参照元:")
    for i, (doc, score) in enumerate(chunks, 1):
        source = doc.metadata.get('source', '不明')
        chunk_id = doc.metadata.get('chunk_id', '不明')
        similarity = 1 - score  # スコアを類似度に変換
        print(f"  [{i}] {source} (チャンクID: {chunk_id}, 類似度: {similarity:.3f})")
    print("=" * 60)


if __name__ == "__main__":
    main()

