#!/usr/bin/env python3
"""
FAQ Bot for Slack with Hybrid Search
ハイブリッド検索を使用したSlack Bot

リファクタリング済み:
- 設定はconfig.pyに分離
- プロンプトはprompts/に分離
- 共通関数はutils.pyに分離
"""

import os
import re
import json
from typing import Tuple, List, Dict

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from hybrid_search import HybridSearchRetriever

# 設定とユーティリティのインポート
from config import (
    SLACK_BOT_TOKEN,
    SLACK_APP_TOKEN,
    OPENAI_API_KEY,
    GOOGLE_API_KEY,
    CHROMA_DB_DIR,
    TOP_K_RESULTS,
    SEARCH_MULTIPLIER,
    MAX_CLARIFYING_QUESTIONS,
    CLARITY_CHECK_TEMPERATURE,
    ANSWER_GENERATION_TEMPERATURE,
    LAW_TYPES,
    LAW_SOURCE_MAPPING,
    EMBEDDING_MODEL,
    GENERATION_MODEL,
    HEALTH_CHECK_FILE
)

from utils import (
    get_clarity_check_prompt,
    get_clarity_recheck_prompt,
    get_answer_generation_prompt,
    format_docs,
    format_references,
    create_clarification_message,
    create_further_clarification_message,
    format_response_with_references
)

# スレッドコンテキスト管理（追加質問の履歴を保持）
thread_contexts: Dict[str, Dict] = {}

# Slack Appの初期化
app = App(token=SLACK_BOT_TOKEN)


# ========================
# データベース初期化
# ========================

def load_vectordb_with_hybrid_search():
    """ベクトルDBを読み込み、ハイブリッド検索retrieverを作成"""
    print("  [1/4] 埋め込みモデルを初期化中...")
    embedding_model = OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=OPENAI_API_KEY
    )
    
    print("  [2/4] ベクトルDBを読み込み中...")
    vectordb = Chroma(
        persist_directory=CHROMA_DB_DIR,
        embedding_function=embedding_model
    )
    
    print("  [3/4] 全ドキュメントを取得中（BM25インデックス構築のため）...")
    print("  ※ この処理には時間がかかる場合があります")
    
    print("  [4/4] ハイブリッド検索retrieverを構築中...")
    hybrid_retriever = HybridSearchRetriever(
        vectordb=vectordb,
        alpha=0.5  # BM25とベクトル検索を同じ重みで
    )
    
    print("  ✓ 初期化完了")
    return hybrid_retriever


# ========================
# 質問の具体性チェック
# ========================


def check_question_clarity(question: str, law_type: str) -> dict:
    """
    質問の具体性をチェックし、曖昧な場合は追加質問を生成
    
    Returns:
        dict: {
            "is_clear": bool,
            "missing_aspects": list,
            "clarifying_questions": list
        }
    """
    # LLMの初期化（厳格な判定のため低温度）
    llm = ChatGoogleGenerativeAI(
        model=GENERATION_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=CLARITY_CHECK_TEMPERATURE,
    )
    
    # プロンプトの作成（utils経由で読み込み）
    prompt = PromptTemplate.from_template(get_clarity_check_prompt())
    
    # チェーンの構築
    chain = (
        {
            "question": lambda x: x,
            "law_type": lambda x: law_type
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    
    try:
        # LLMで質問の具体性を判定
        result = chain.invoke({"question": question, "law_type": law_type})
        
        print(f"  [LLM判定結果（生）]: {result[:200]}...")  # デバッグ用
        
        # JSON部分を抽出（マークダウンのコードブロックを除去）
        json_match = re.search(r'\{[^{}]*"is_clear"[^{}]*\}', result, re.DOTALL)
        if json_match:
            result = json_match.group(0)
        
        # JSONをパース
        clarity_result = json.loads(result)
        
        print(f"  [判定結果] is_clear={clarity_result.get('is_clear')}, missing={clarity_result.get('missing_aspects')}")
        
        return clarity_result
        
    except Exception as e:
        print(f"質問の具体性チェックでエラー: {e}")
        print(f"  エラー詳細: result={result if 'result' in locals() else 'N/A'}")
        # エラー時は曖昧と判定（安全側に倒す）
        return {
            "is_clear": False,
            "missing_aspects": ["エラーが発生したため判定できませんでした"],
            "clarifying_questions": [
                "質問をより具体的に記述していただけますか？",
                "具体的な金額や数値はありますか？",
                "誰が、どのような状況で行うことについて知りたいですか？"
            ]
        }


def recheck_question_with_additional_info(original_question: str, additional_info: list, law_type: str) -> dict:
    """
    追加情報を含めて質問の具体性を再チェック
    
    Returns:
        dict: {
            "is_now_clear": bool,
            "still_missing_aspects": list,
            "next_clarifying_questions": list,
            "combined_question": str
        }
    """
    # LLMの初期化
    llm = ChatGoogleGenerativeAI(
        model=GENERATION_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=CLARITY_CHECK_TEMPERATURE,
    )
    
    # 追加情報を整形
    additional_info_text = "\n".join([f"- {info}" for info in additional_info])
    
    # プロンプトの作成（utils経由で読み込み）
    prompt = PromptTemplate.from_template(get_clarity_recheck_prompt())
    
    # チェーンの構築
    chain = (
        {
            "original_question": lambda x: original_question,
            "additional_info": lambda x: additional_info_text,
            "law_type": lambda x: law_type
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    
    try:
        # LLMで再評価
        result = chain.invoke({"original_question": original_question, "additional_info": additional_info_text, "law_type": law_type})
        
        print(f"  [再評価結果（生）]: {result[:200]}...")
        
        # JSON部分を抽出
        json_match = re.search(r'\{[^{}]*"is_now_clear"[^{}]*\}', result, re.DOTALL)
        if json_match:
            result = json_match.group(0)
        
        # JSONをパース
        recheck_result = json.loads(result)
        
        print(f"  [再評価判定] is_now_clear={recheck_result.get('is_now_clear')}, still_missing={recheck_result.get('still_missing_aspects')}")
        
        return recheck_result
        
    except Exception as e:
        print(f"質問の再評価でエラー: {e}")
        print(f"  エラー詳細: result={result if 'result' in locals() else 'N/A'}")
        # エラー時は不足と判定
        return {
            "is_now_clear": False,
            "still_missing_aspects": ["エラーが発生したため判定できませんでした"],
            "next_clarifying_questions": [
                "もう少し具体的な情報を教えていただけますか？"
            ],
            "combined_question": f"{original_question} 【追加情報】 {'; '.join(additional_info)}"
        }


# ========================
# 回答生成（質問の具体性チェック付き/なし）
# ========================

def generate_answer_directly(query: str, hybrid_retriever, law_type: str = "景表法"):
    """質問の具体性チェックをスキップして直接回答を生成（追加情報統合後用）"""
    
    print(f"  [直接回答生成] 質問: {query}")
    
    # 1. 検索クエリを拡張（法律名と適用除外キーワードを追加して精度向上）
    enhanced_query = f"{law_type} {query} 適用除外"
    
    # 2. ハイブリッド検索を実行（多めに取得してフィルタリング）
    docs_and_scores = hybrid_retriever.search(enhanced_query, k=TOP_K_RESULTS * SEARCH_MULTIPLIER)
    
    # 3. メタデータでフィルタリング（選択された法律のドキュメントのみ）
    relevant_sources = LAW_SOURCE_MAPPING.get(law_type, [])
    if relevant_sources:
        filtered_docs = [
            (doc, score) for doc, score in docs_and_scores 
            if any(source in doc.metadata.get('source', '') for source in relevant_sources)
        ][:TOP_K_RESULTS]
    else:
        filtered_docs = docs_and_scores[:TOP_K_RESULTS]
    
    docs = [doc for doc, score in filtered_docs]
    
    # LLMの初期化
    llm = ChatGoogleGenerativeAI(
        model=GENERATION_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=ANSWER_GENERATION_TEMPERATURE,
    )
    
    # プロンプトの作成（utils経由で読み込み）
    prompt = PromptTemplate.from_template(get_answer_generation_prompt())
    
    # RAGチェーンの構築
    rag_chain = (
        {
            "context": lambda x: format_docs(docs),
            "question": lambda x: query,  # 元のクエリを使用
            "law_type": lambda x: law_type
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    
    # 回答の生成
    answer = rag_chain.invoke(query)
    
    # 参照元情報の整形（Slack用、utils関数を使用）
    references = format_references(filtered_docs)
    
    return answer, references


def generate_answer(query: str, hybrid_retriever, law_type: str = "景表法"):
    """質問に対して回答を生成（法律タイプでフィルタリング・拡張）"""
    
    # ステップ1: 質問の具体性をチェック
    print(f"  [質問の具体性をチェック中...] 質問: {query}")
    clarity_result = check_question_clarity(query, law_type)
    
    # ステップ2: 質問が曖昧な場合は追加ヒアリング
    if not clarity_result.get("is_clear", True):
        print(f"  [判定] 質問が曖昧 - 追加ヒアリングを実施")
        
        clarifying_questions = clarity_result.get("clarifying_questions", [])
        
        # 追加ヒアリングのメッセージを生成（utils関数を使用）
        clarification_message = create_clarification_message(
            clarifying_questions,
            law_type,
            max_questions=MAX_CLARIFYING_QUESTIONS
        )
        
        # 追加ヒアリングの場合は参照なし
        return clarification_message, []
    
    # ステップ3: 質問が具体的な場合は回答を生成
    print(f"  [判定] 質問が具体的 - 回答を生成します")
    
    # 1. 検索クエリを拡張（法律名と適用除外キーワードを追加して精度向上）
    enhanced_query = f"{law_type} {query} 適用除外"
    
    # 2. ハイブリッド検索を実行（多めに取得してフィルタリング）
    docs_and_scores = hybrid_retriever.search(enhanced_query, k=TOP_K_RESULTS * SEARCH_MULTIPLIER)
    
    # 3. メタデータでフィルタリング（選択された法律のドキュメントのみ）
    relevant_sources = LAW_SOURCE_MAPPING.get(law_type, [])
    if relevant_sources:
        filtered_docs = [
            (doc, score) for doc, score in docs_and_scores 
            if any(source in doc.metadata.get('source', '') for source in relevant_sources)
        ][:TOP_K_RESULTS]
    else:
        filtered_docs = docs_and_scores[:TOP_K_RESULTS]
    
    docs = [doc for doc, score in filtered_docs]
    
    # LLMの初期化
    llm = ChatGoogleGenerativeAI(
        model=GENERATION_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=ANSWER_GENERATION_TEMPERATURE,
    )
    
    # プロンプトの作成（utils経由で読み込み）
    prompt = PromptTemplate.from_template(get_answer_generation_prompt())
    
    # RAGチェーンの構築
    rag_chain = (
        {
            "context": lambda x: format_docs(docs),
            "question": lambda x: query,  # 元のクエリを使用
            "law_type": lambda x: law_type
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    
    # 回答の生成
    answer = rag_chain.invoke(query)
    
    # 参照元情報の整形（Slack用、utils関数を使用）
    references = format_references(filtered_docs)
    
    return answer, references


# ========================
# Slack UIコンポーネント
# ========================

def create_law_selection_blocks(question: str):
    """法律選択ボタンを含むSlack Blocksを作成"""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*どの法律に関する質問ですか？*\n\n質問: _{question}_"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "📜 景表法"
                    },
                    "action_id": "select_law_keihyouhou",
                    "value": f"keihyouhou|||{question}"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "💰 資金決済法"
                    },
                    "action_id": "select_law_shikin_kessai",
                    "value": f"shikin_kessai|||{question}"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "🔐 個人情報保護法"
                    },
                    "action_id": "select_law_kojin_jouhou",
                    "value": f"kojin_jouhou|||{question}"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "📝 印紙税法"
                    },
                    "action_id": "select_law_inshi_zei",
                    "value": f"inshi_zei|||{question}"
                }
            ]
        }
    ]


# ========================
# Slackイベントハンドラー
# ========================

@app.event("app_mention")
def handle_mention(event, say):
    """ボットがメンションされた時の処理"""
    try:
        # メンションを除去して質問を抽出
        text = event['text']
        question = re.sub(r'<@[A-Z0-9]+>', '', text).strip()
        
        # メッセージのタイムスタンプを取得（スレッド用）
        thread_ts = event['ts']
        
        if not question:
            say("質問を入力してください。例: @FAQ Bot 景品類の定義を教えてください", thread_ts=thread_ts)
            return
        
        # 法律選択ボタンをスレッドに送信
        say(
            blocks=create_law_selection_blocks(question),
            text=f"どの法律に関する質問ですか？\n質問: {question}",
            thread_ts=thread_ts
        )
        
    except Exception as e:
        # エラーもスレッドに送信
        thread_ts = event.get('ts')
        say(f"申し訳ございません。エラーが発生しました: {str(e)}", thread_ts=thread_ts)


@app.message("")
def handle_message(message, say, client):
    """DMや通常のメッセージへの応答、およびスレッド内の追加情報の処理"""
    print(f"  [handle_message呼び出し] message={message.get('text', '')[:50]}, channel_type={message.get('channel_type', 'N/A')}, bot_id={message.get('bot_id', 'N/A')}, thread_ts={message.get('thread_ts', 'N/A')}")
    
    # ボットの投稿は無視
    if message.get('bot_id'):
        print(f"  [スキップ] ボットの投稿")
        return
    
    # スレッド内のメッセージかチェック
    thread_ts = message.get('thread_ts')
    print(f"  [チェック] thread_ts={thread_ts}, contexts={list(thread_contexts.keys())}")
    
    # スレッド内のメッセージで、コンテキストがある場合は追加情報として処理
    if thread_ts and thread_ts in thread_contexts:
        try:
            context = thread_contexts[thread_ts]
            user_response = message['text'].strip()
            
            if not user_response:
                return
            
            print(f"  [スレッド内応答検知] thread_ts={thread_ts}, response={user_response}")
            
            # 追加情報を記録
            context['additional_info'].append(user_response)
            
            # 「確認中」メッセージを送信
            say(f"🤔 追加情報を確認しています...\n> {user_response}", thread_ts=thread_ts)
            
            # 追加情報を含めて再評価
            recheck_result = recheck_question_with_additional_info(
                context['original_question'],
                context['additional_info'],
                context['law_type']
            )
            
            # 十分に具体的になった場合
            if recheck_result.get('is_now_clear', False):
                combined_question = recheck_result.get('combined_question', context['original_question'])
                
                say(
                    f"✅ **情報が揃いました！回答を生成します**\n\n統合された質問:\n> {combined_question}",
                    thread_ts=thread_ts
                )
                
                # 統合された質問で回答を生成（具体性チェックをスキップして直接回答）
                print(f"  [統合質問で回答生成] {combined_question}")
                law_type = context['law_type']
                answer, references = generate_answer_directly(combined_question, hybrid_retriever, law_type)
                
                # 回答を送信（utils関数を使用）
                response_text = format_response_with_references(answer, references, law_type)
                say(response_text, thread_ts=thread_ts)
                
                # コンテキストをクリア
                del thread_contexts[thread_ts]
                print(f"  [スレッドコンテキスト削除] thread_ts={thread_ts}")
                
            else:
                # まだ不足している場合は追加質問（utils関数を使用）
                still_missing = recheck_result.get('still_missing_aspects', [])
                next_questions = recheck_result.get('next_clarifying_questions', [])
                
                clarification_message = create_further_clarification_message(
                    next_questions,
                    still_missing,
                    max_questions=MAX_CLARIFYING_QUESTIONS
                )
                
                say(clarification_message, thread_ts=thread_ts)
            
            return
            
        except Exception as e:
            print(f"スレッド内メッセージ処理エラー: {e}")
            import traceback
            traceback.print_exc()
            say(f"申し訳ございません。エラーが発生しました: {str(e)}", thread_ts=thread_ts)
            return
    
    # チャネルタイプを確認
    channel_type = message.get('channel_type', '')
    
    # DMの場合のみ応答
    if channel_type == 'im':
        try:
            question = message['text'].strip()
            
            if not question:
                return
            
            # 法律選択ボタンを送信
            say(
                blocks=create_law_selection_blocks(question),
                text=f"どの法律に関する質問ですか？\n質問: {question}"
            )
            
        except Exception as e:
            say(f"申し訳ございません。エラーが発生しました: {str(e)}")


# ボタンアクションのハンドラー
@app.action(re.compile("select_law_.*"))
def handle_law_selection(ack, body, say):
    """法律選択ボタンがクリックされた時の処理"""
    # アクションを確認
    ack()
    
    try:
        # ボタンの値から法律タイプと質問を取得
        action_value = body['actions'][0]['value']
        law_key, question = action_value.split('|||', 1)
        law_type = LAW_TYPES.get(law_key, "景表法")
        
        # スレッドのタイムスタンプを取得
        thread_ts = body['message']['thread_ts'] if 'thread_ts' in body['message'] else body['message']['ts']
        
        # 「考え中」メッセージをスレッドに送信
        say(f"🤔 {law_type}に関する質問として回答を生成中...\n> {question}", thread_ts=thread_ts)
        
        # 回答を生成（メタデータフィルタリング付き）
        answer, references = generate_answer(question, hybrid_retriever, law_type)
        
        # 回答が追加質問（参照なし）の場合、スレッドコンテキストを保存
        if not references:  # 追加質問の場合
            thread_contexts[thread_ts] = {
                "original_question": question,
                "law_type": law_type,
                "additional_info": [],
                "last_interaction": body.get('message', {}).get('ts')
            }
            print(f"  [スレッドコンテキスト保存] thread_ts={thread_ts}, question={question}, law_type={law_type}")
        
        # 回答を整形（Slack用、utils関数を使用）
        if references:
            response_text = format_response_with_references(answer, references, law_type)
        else:
            # 追加質問の場合はそのまま
            response_text = answer
        
        # 回答をスレッドに送信
        say(response_text, thread_ts=thread_ts)
        
    except Exception as e:
        thread_ts = body['message'].get('thread_ts') or body['message'].get('ts')
        say(f"申し訳ございません。エラーが発生しました: {str(e)}", thread_ts=thread_ts)


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
    print(f"  - 法律別メタデータフィルタリング有効")
    hybrid_retriever = load_vectordb_with_hybrid_search()
    
    print("\n" + "="*60)
    print("✓ FAQ Bot (ハイブリッド検索版) が起動しました")
    print("="*60)
    print("チャネルで @FAQ Bot をメンションして質問してください")
    print("対応法律: 景表法、資金決済法、個人情報保護法、印紙税法")
    print("BM25 + ベクトル検索 + メタデータフィルタリング")
    print("\n終了するには Ctrl+C を押してください")
    print("="*60 + "\n")
    
    # ヘルスチェック用のファイルを作成（Docker用）
    try:
        with open(HEALTH_CHECK_FILE, 'w') as f:
            f.write('ready')
    except Exception:
        pass  # ローカル環境では/tmpが使えない場合もあるので無視
    
    # Socket Modeで起動
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()

