#!/usr/bin/env python3
"""
FAQ Bot for Slack with Hybrid Search
ハイブリッド検索を使用したSlack Bot
"""

import os
import re
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from hybrid_search import HybridSearchRetriever

# 環境変数の読み込み
load_dotenv()

# Slack設定
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")

# FAQ Bot設定
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
4. Slack用に、箇条書きや段落を見やすく整形してください
5. 全く関連する情報がない場合は、「提供された情報には、この質問に対する回答が含まれていません」と答えてください
6. 法律条文、施行規則、FAQ それぞれの情報を区別して活用し、包括的な回答を提供してください

# コンテキスト情報
{context}

# 質問
{question}

# 回答（必ず参照元を明示してください）
"""

# Slack Appの初期化
app = App(token=SLACK_BOT_TOKEN)


# ベクトルDBとハイブリッド検索の初期化
def load_vectordb_with_hybrid_search():
    """ベクトルDBを読み込み、ハイブリッド検索retrieverを作成"""
    embedding_model = OpenAIEmbeddings(
        model="text-embedding-3-large",
        openai_api_key=OPENAI_API_KEY
    )
    
    vectordb = Chroma(
        persist_directory=CHROMA_DB_DIR,
        embedding_function=embedding_model
    )
    
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


def generate_answer(query: str, hybrid_retriever):
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
    
    # 参照元情報の整形（Slack用）
    references = []
    for i, (doc, score) in enumerate(docs_and_scores, 1):
        source = doc.metadata.get('source', '不明')
        
        # ファイル名を短縮
        if 'Q&A' in source:
            source_label = "FAQ"
        elif '施行規則' in source:
            source_label = "施行規則"
        elif '不当景品類及び不当表示防止法.pdf' in source:
            source_label = ":law: 景表法"
        else:
            source_label = source
        
        hybrid_score = doc.metadata.get('hybrid_score', 0)
        references.append(f"[{i}] {source_label} (スコア: {hybrid_score:.3f})")
    
    return answer, references


# Slackイベントハンドラー
@app.event("app_mention")
def handle_mention(event, say):
    """ボットがメンションされた時の処理"""
    try:
        # メンションを除去して質問を抽出
        text = event['text']
        question = re.sub(r'<@[A-Z0-9]+>', '', text).strip()
        
        if not question:
            say("質問を入力してください。例: @FAQ Bot 景品類の定義を教えてください")
            return
        
        # 「考え中」メッセージを送信
        say(f"🤔 質問を確認しています...\n> {question}")
        
        # 回答を生成
        answer, references = generate_answer(question, hybrid_retriever)
        
        # 回答を整形（Slack用）
        response_text = f"*📝 回答:*\n{answer}\n\n*📚 参照元 (法律・施行規則・FAQ):*\n"
        for ref in references:
            response_text += f"  • {ref}\n"
        
        # 回答を送信
        say(response_text)
        
    except Exception as e:
        say(f"申し訳ございません。エラーが発生しました: {str(e)}")


@app.message("")
def handle_message(message, say):
    """DMや通常のメッセージへの応答"""
    # ボットの投稿は無視
    if message.get('bot_id'):
        return
    
    # チャネルタイプを確認
    channel_type = message.get('channel_type', '')
    
    # DMの場合のみ応答
    if channel_type == 'im':
        try:
            question = message['text'].strip()
            
            if not question:
                return
            
            # 「考え中」メッセージを送信
            say(f"🤔 質問を確認しています...\n> {question}")
            
            # 回答を生成
            answer, references = generate_answer(question, hybrid_retriever)
            
            # 回答を整形
            response_text = f"*📝 回答:*\n{answer}\n\n*📚 参照元:*\n"
            for ref in references:
                response_text += f"  • {ref}\n"
            
            # 回答を送信
            say(response_text)
            
        except Exception as e:
            say(f"申し訳ございません。エラーが発生しました: {str(e)}")


if __name__ == "__main__":
    # 環境変数のチェック
    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        print("エラー: SLACK_BOT_TOKEN と SLACK_APP_TOKEN を .env ファイルに設定してください")
        exit(1)
    
    if not OPENAI_API_KEY or not GOOGLE_API_KEY:
        print("エラー: OPENAI_API_KEY と GOOGLE_API_KEY を .env ファイルに設定してください")
        exit(1)
    
    if not os.path.exists(CHROMA_DB_DIR):
        print(f"エラー: ベクトルDB ({CHROMA_DB_DIR}) が見つかりません")
        print("まず prepare_database_openai.py を実行してベクトルDBを作成してください")
        exit(1)
    
    # ベクトルDBとハイブリッド検索の初期化
    print("FAQ Bot (ハイブリッド検索版) を起動中...")
    print(f"  - ハイブリッドスコア上位{TOP_K_RESULTS}件を取得")
    hybrid_retriever = load_vectordb_with_hybrid_search()
    
    print("\n" + "="*60)
    print("✓ FAQ Bot (ハイブリッド検索版) が起動しました")
    print("="*60)
    print("チャネルで @FAQ Bot をメンションして質問してください")
    print("BM25 + ベクトル検索で最適な情報を取得します")
    print("\n終了するには Ctrl+C を押してください")
    print("="*60 + "\n")
    
    # Socket Modeで起動
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()

