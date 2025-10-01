#!/usr/bin/env python3
"""
FAQ Bot for Slack (Debug版)
詳細なログを出力してデバッグします
"""

import os
import re
import logging
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.vectorstores import Chroma

# ログ設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
logger.info("Slack Appを初期化中...")
app = App(token=SLACK_BOT_TOKEN)

# ベクトルDBの初期化
logger.info("ベクトルDBを読み込み中...")
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

logger.info("✓ FAQ Botの準備が完了しました")


def search_and_answer(question: str) -> tuple[str, list]:
    """質問に対する回答を生成"""
    logger.info(f"質問を処理中: {question}")
    
    # 関連チャンクの検索
    results = vectordb.similarity_search_with_score(question, k=TOP_K_RESULTS)
    
    if not results:
        logger.warning("関連する情報が見つかりませんでした")
        return "関連する情報が見つかりませんでした。", []
    
    logger.info(f"{len(results)}個の関連チャンクが見つかりました")
    
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
    logger.info("LLMで回答を生成中...")
    response = llm.invoke(prompt)
    
    # 参照元情報の整形
    references = []
    for i, (doc, score) in enumerate(results, 1):
        source = doc.metadata.get('source', '不明')
        chunk_id = doc.metadata.get('chunk_id', '不明')
        similarity = 1 - score
        references.append(f"[{i}] {source} (類似度: {similarity:.3f})")
    
    logger.info("回答生成完了")
    return response.content, references


@app.event("app_mention")
def handle_mention(event, say):
    """ボットがメンションされた時の処理"""
    logger.info("=" * 60)
    logger.info("app_mentionイベントを受信しました")
    logger.info(f"イベント内容: {event}")
    logger.info("=" * 60)
    
    try:
        # メンションを除去して質問を抽出
        text = event['text']
        logger.info(f"受信したテキスト: {text}")
        
        # <@U...> の形式のメンションを除去
        question = re.sub(r'<@[A-Z0-9]+>', '', text).strip()
        logger.info(f"抽出した質問: {question}")
        
        if not question:
            logger.warning("質問が空です")
            say("質問を入力してください。例: @FAQ Bot 景品類の定義を教えてください")
            return
        
        # 「考え中」メッセージを送信
        logger.info("考え中メッセージを送信...")
        say(f"🤔 質問を確認しています...\n> {question}")
        
        # 回答を生成
        logger.info("回答を生成中...")
        answer, references = search_and_answer(question)
        
        # 回答を整形
        response_text = f"*回答:*\n{answer}\n\n*参照元:*\n"
        for ref in references:
            response_text += f"• {ref}\n"
        
        # 回答を送信
        logger.info("回答を送信中...")
        say(response_text)
        logger.info("✓ 回答送信完了")
        
    except Exception as e:
        logger.error(f"エラーが発生しました: {str(e)}", exc_info=True)
        say(f"申し訳ございません。エラーが発生しました: {str(e)}")


@app.message("")
def handle_message(message, say):
    """DMや通常のメッセージへの応答"""
    logger.debug(f"メッセージイベント受信: {message}")
    
    # ボットの投稿は無視
    if message.get('bot_id'):
        logger.debug("ボットのメッセージなので無視")
        return
    
    # チャネルタイプを確認
    channel_type = message.get('channel_type', '')
    logger.debug(f"チャネルタイプ: {channel_type}")
    
    # DMの場合のみ応答（チャネルではメンション必須）
    if channel_type == 'im':
        logger.info("DMメッセージを処理中")
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
            logger.error(f"エラーが発生しました: {str(e)}", exc_info=True)
            say(f"申し訳ございません。エラーが発生しました: {str(e)}")


@app.event("message")
def handle_message_events(body, logger):
    """メッセージイベントの処理（ログ用）"""
    logger.debug(f"messageイベント: {body}")


if __name__ == "__main__":
    # 環境変数のチェック
    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        logger.error("SLACK_BOT_TOKEN と SLACK_APP_TOKEN を .env ファイルに設定してください")
        exit(1)
    
    if not OPENAI_API_KEY or not GOOGLE_API_KEY:
        logger.error("OPENAI_API_KEY と GOOGLE_API_KEY を .env ファイルに設定してください")
        exit(1)
    
    if not os.path.exists(CHROMA_DB_DIR):
        logger.error(f"ベクトルDB ({CHROMA_DB_DIR}) が見つかりません")
        exit(1)
    
    print("\n" + "="*60)
    print("✓ FAQ Bot (Debug版) が起動しました")
    print("="*60)
    print("チャネルで @FAQ Bot をメンションして質問してください")
    print("ログを確認しながら動作を確認できます")
    print("\n終了するには Ctrl+C を押してください")
    print("="*60 + "\n")
    
    # Socket Modeで起動
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()

