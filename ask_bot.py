#!/usr/bin/env python3
"""
FAQボット - 質問応答スクリプト
ベクトルDBから関連情報を検索し、LLMで回答を生成します。
"""

import os
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
あなたは法律やFAQに関する質問に回答する親切なアシスタントです。
以下のコンテキスト情報だけを元にして、質問に日本語で回答してください。
コンテキストに答えがない場合は、「分かりません」と回答してください。

# コンテキスト
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
    print("=== FAQボット ===")
    print("質問を入力してください（終了するには 'quit' または 'exit' と入力）\n")
    
    # 環境変数のチェック
    if not GOOGLE_API_KEY:
        print("エラー: .envファイルにGOOGLE_API_KEYを設定してください。")
        return
    
    # ベクトルDBの読み込み
    print("ベクトルDBを読み込み中...")
    vectordb = load_vectordb()
    if vectordb is None:
        return
    
    print("準備完了！質問を入力してください。\n")
    
    # 対話ループ
    while True:
        try:
            # 質問の入力
            query = input("質問: ").strip()
            
            # 終了判定
            if query.lower() in ['quit', 'exit', '終了']:
                print("ボットを終了します。")
                break
            
            if not query:
                continue
            
            print("\n検索中...")
            
            # 関連チャンクの検索
            relevant_chunks = search_relevant_chunks(vectordb, query)
            
            if not relevant_chunks:
                print("回答: 関連する情報が見つかりませんでした。\n")
                continue
            
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
            print()
            
        except KeyboardInterrupt:
            print("\n\nボットを終了します。")
            break
        except Exception as e:
            print(f"\nエラーが発生しました: {str(e)}\n")


if __name__ == "__main__":
    main()

