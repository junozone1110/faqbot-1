#!/usr/bin/env python3
"""
FAQ Bot for Slack
Slackチャネルで質問に回答するボットアプリケーション
"""

import os
import re
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.vectorstores import Chroma

# 環境変数の読み込み
load_dotenv()

# Slack設定
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")

# FAQ Bot設定
CHROMA_DB_DIR = "./chroma_db_openai"
TOP_K_RESULTS = 5
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

# コンテキスト情報
{context}

# 質問
{question}

# 回答（必ず参照元を明示してください）
"""

# Slack Appの初期化
app = App(token=SLACK_BOT_TOKEN)

# ベクトルDBの初期化
print("ベクトルDBを読み込み中...")
embedding_model = OpenAIEmbeddings(
    model="text-embedding-3-large",
    openai_api_key=OPENAI_API_KEY
)

vectordb = Chroma(
    persist_directory=CHROMA_DB_DIR,
    embedding_function=embedding_model
)

# LLMの初期化
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=GOOGLE_API_KEY,
    temperature=0.2,
)

print("✓ FAQ Botの準備が完了しました")


def search_and_answer(question: str) -> tuple[str, list]:
    """質問に対する回答を生成"""
    # 関連チャンクの検索
    results = vectordb.similarity_search_with_score(question, k=TOP_K_RESULTS)
    
    if not results:
        return "関連する情報が見つかりませんでした。", []
    
    # コンテキストの作成
    context_parts = []
    for i, (doc, score) in enumerate(results, 1):
        source = doc.metadata.get('source', '不明')
        chunk_id = doc.metadata.get('chunk_id', '不明')
        context_parts.append(f"[参照{i}] (出典: {source}, ID: {chunk_id})\n{doc.page_content}\n")
    
    context = "\n".join(context_parts)
    
    # プロンプトの組み立て
    prompt = PROMPT_TEMPLATE.format(context=context, question=question)
    
    # 回答生成
    response = llm.invoke(prompt)
    
    # 参照元情報の整形
    references = []
    for i, (doc, score) in enumerate(results, 1):
        source = doc.metadata.get('source', '不明')
        chunk_id = doc.metadata.get('chunk_id', '不明')
        similarity = 1 - score
        references.append(f"[{i}] {source} (類似度: {similarity:.3f})")
    
    return response.content, references


@app.event("app_mention")
def handle_mention(event, say):
    """ボットがメンションされた時の処理"""
    try:
        # メンションを除去して質問を抽出
        text = event['text']
        # <@U...> の形式のメンションを除去
        question = re.sub(r'<@[A-Z0-9]+>', '', text).strip()
        
        if not question:
            say("質問を入力してください。例: @FAQ Bot 景品類の定義を教えてください")
            return
        
        # 「考え中」メッセージを送信
        say(f"🤔 質問を確認しています...\n> {question}")
        
        # 回答を生成
        answer, references = search_and_answer(question)
        
        # 回答を整形
        response_text = f"*回答:*\n{answer}\n\n*参照元:*\n"
        for ref in references:
            response_text += f"• {ref}\n"
        
        # 回答を送信
        say(response_text)
        
    except Exception as e:
        print(f"エラー: {str(e)}")
        say(f"申し訳ございません。エラーが発生しました: {str(e)}")


@app.message("")
def handle_message(message, say):
    """DMや通常のメッセージへの応答"""
    # ボットの投稿は無視
    if message.get('bot_id'):
        return
    
    # チャネルタイプを確認
    channel_type = message.get('channel_type', '')
    
    # DMの場合のみ応答（チャネルではメンション必須）
    if channel_type == 'im':
        try:
            question = message['text'].strip()
            
            if not question:
                return
            
            # 「考え中」メッセージを送信
            say(f"🤔 質問を確認しています...\n> {question}")
            
            # 回答を生成
            answer, references = search_and_answer(question)
            
            # 回答を整形
            response_text = f"*回答:*\n{answer}\n\n*参照元:*\n"
            for ref in references:
                response_text += f"• {ref}\n"
            
            # 回答を送信
            say(response_text)
            
        except Exception as e:
            print(f"エラー: {str(e)}")
            say(f"申し訳ございません。エラーが発生しました: {str(e)}")


@app.event("message")
def handle_message_events(body, logger):
    """メッセージイベントの処理（ログ用）"""
    logger.debug(body)


if __name__ == "__main__":
    # 環境変数のチェック
    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        print("エラー: SLACK_BOT_TOKEN と SLACK_APP_TOKEN を .env ファイルに設定してください")
        print("\n設定方法については SLACK_SETUP.md を参照してください")
        exit(1)
    
    if not OPENAI_API_KEY or not GOOGLE_API_KEY:
        print("エラー: OPENAI_API_KEY と GOOGLE_API_KEY を .env ファイルに設定してください")
        exit(1)
    
    if not os.path.exists(CHROMA_DB_DIR):
        print(f"エラー: ベクトルDB ({CHROMA_DB_DIR}) が見つかりません")
        print("先に prepare_database_openai.py を実行してください")
        exit(1)
    
    print("\n" + "="*60)
    print("✓ FAQ Bot が起動しました")
    print("="*60)
    print("チャネルで @FAQ Bot をメンションして質問してください")
    print("または、ボットにDMを送信してください")
    print("\n終了するには Ctrl+C を押してください")
    print("="*60 + "\n")
    
    # Socket Modeで起動
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()

