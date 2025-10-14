#!/usr/bin/env python3
"""
FAQ Bot for Slack with Hybrid Search
ハイブリッド検索を使用したSlack Bot
"""

import os
import re
import json
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

# スレッドコンテキスト管理（追加質問の履歴を保持）
thread_contexts = {}

# 法律の種類マッピング
LAW_TYPES = {
    "keihyouhou": "景表法",
    "shikin_kessai": "資金決済法",
    "kojin_jouhou": "個人情報保護法",
    "inshi_zei": "印紙税法"
}

# 法律とソースファイルのマッピング（メタデータフィルタリング用）
LAW_SOURCE_MAPPING = {
    "景表法": [
        "不当景品類及び不当表示防止法.pdf",
        "不当景品類及び不当表示防止法施行規則.pdf",
        "景品に関するQ&A.pdf"
    ],
    "資金決済法": [
        "資金決済に関する法律.pdf",
        "資金決済に関する法律施行令.pdf",
        "前払式支払手段についてよくあるご質問231027.pdf"
    ],
    "個人情報保護法": [
        "個人情報の保護に関する法律.pdf",
        "個人情報の保護に関する法律施行規則.pdf",
        "個人情報保護委員会ガイドライン通則編.pdf",
        "個人情報の保護に関する法律についてのガイドライン.pdf",
        "個人情報の保護に関する法律についてのガイドライン （仮名加工情報・匿名加工情報編）.pdf",
        "個人情報の保護に関する法律についてのガイドライン （第三者提供時の確認・記録義務編）.pdf",
        "「個人情報の保護に関する法律についてのガイドライン」 に関するＱ＆Ａ.pdf"
    ],
    "印紙税法": [
        "印紙税法.pdf",
        "印紙一覧.pdf"
    ]
}

# 質問の曖昧さチェック用プロンプト
CLARITY_CHECK_PROMPT = """
あなたは法律相談における質問の具体性を評価する厳格な専門家です。
以下の質問が「{law_type}」に関する法律相談として十分に具体的かどうかを評価してください。

**重要な前提**:
法律の適用判断や法的評価を求める質問の場合、以下の具体的情報がほぼ必須です：
- 金額・規模（数値）
- 具体的な主体（誰が、どのような立場で）
- 具体的な状況・行為の内容
- 時期・期間（該当する場合）

**評価基準**:
質問には以下の観点が含まれているべきです：

1. **What（何を）** - 必須
   - 具体的なトピック、用語、制度、行為が明確か
   - 単なる一般名詞ではなく、具体的な内容が特定できるか

2. **Who（誰が）** - 法律適用判断には必須
   - 主体の立場（事業者/消費者/個人/法人）
   - 事業形態、規模など

3. **How much（いくら）** - 金額基準がある法律では必須
   - 金額、規模、数量などの具体的な数値

4. **Context（状況）** - 法律適用判断には必須
   - 具体的な状況、使用方法、目的
   - 該当する条件や前提

**厳格な判定ルール**:

✅ **具体的と判定する条件**:
- 用語の定義を聞いている（例：「景品類の定義は？」）
- 特定の条文や制度の解説を求めている
- 手続きの方法を聞いている
- 上記の必要情報がすべて含まれている具体的なケースの相談

❌ **曖昧と判定する条件（以下のいずれかに該当）**:
- 「〜は適用される？」「〜に該当する？」という法律適用の判断を求めているが、判断に必要な具体的情報（金額、主体、状況など）が不足
- 抽象的な一般名詞のみで、具体的な内容が不明（例：「電子チケット」「ポイント」だけでは不十分）
- 「について教えて」「詳しく知りたい」だけで範囲が広すぎる
- 法律の適用可否を聞いているのに、Who（誰が）やHow much（いくら）が不明

**特に注意**:
- 「{law_type}」に適用されるか判断を求める質問は、判断に必要な具体的情報がすべて揃っていない限り曖昧と判定してください
- 資金決済法や印紙税法など金額基準がある法律の場合、金額情報がない適用判断の質問は必ず曖昧と判定してください

# 質問
{question}

# 出力形式（以下のJSON形式で出力してください）
{{
  "is_clear": true または false,
  "missing_aspects": ["不足している観点のリスト"],
  "clarifying_questions": ["具体化のための質問1", "具体化のための質問2", "具体化のための質問3"]
}}

**重要**: 必ずJSON形式で出力してください。他の説明は不要です。
"""

# 追加情報を含めた質問の再評価用プロンプト
CLARITY_RECHECK_PROMPT = """
あなたは法律相談における質問の具体性を評価する厳格な専門家です。

ユーザーが最初に曖昧な質問をし、追加情報を提供しました。
元の質問と追加情報を組み合わせて、「{law_type}」に関する法律相談として十分に具体的になったかどうかを評価してください。

# 元の質問
{original_question}

# ユーザーが提供した追加情報
{additional_info}

**評価基準**:
法律の適用判断や法的評価を求める質問の場合、以下の具体的情報が必要です：
- 金額・規模（数値）
- 具体的な主体（誰が、どのような立場で）
- 具体的な状況・行為の内容
- 時期・期間（該当する場合）

**判定ルール**:

✅ **十分に具体的と判定する条件**:
- 上記の必要情報がすべて提供された
- 法律適用の判断に必要な具体的な数値、主体、状況が明確になった

❌ **まだ不足していると判定する条件**:
- 重要な情報（特に金額、主体、具体的状況）がまだ不足している
- 提供された情報が抽象的で、判断に使えない

**特に注意**:
- 資金決済法や印紙税法など金額基準がある法律の場合、金額情報は必須
- 「事業者」「会社」だけでは不十分な場合があり、事業形態や規模が必要なケースもある

# 出力形式（以下のJSON形式で出力してください）
{{
  "is_now_clear": true または false,
  "still_missing_aspects": ["まだ不足している観点のリスト（空の場合は十分）"],
  "next_clarifying_questions": ["さらに必要な質問1", "質問2", "質問3"],
  "combined_question": "元の質問と追加情報を統合した完全な質問文"
}}

**重要**: 必ずJSON形式で出力してください。他の説明は不要です。
"""

# 回答生成用プロンプト
PROMPT_TEMPLATE = """
あなたは法律やFAQに関する質問に回答する親切なアシスタントです。
今回の質問は「{law_type}」に関する質問です。

**重要**: 回答は必ず「{law_type}」の観点から行ってください。
他の法律の情報が含まれている場合は、「{law_type}」に関連する部分のみに焦点を当ててください。

以下のコンテキスト情報を参考にして、質問に日本語で分かりやすく回答してください。

**回答の構成**:
まず「📌 要約 ({law_type})」として、最も類似度が高い参照文書（[参照1]または[参照2]）から、質問に直接関連する部分を抜粋・要約してください。
この要約では、文書の内容をそのまま伝え、独自の解釈や推測は一切加えないでください。
その後、詳細な説明を記載してください。

**重要な指示**:
1. **要約セクション**:
   - 冒頭に「📌 要約 ({law_type})」として、参照文書からの直接的な内容のみを記載
   - 文書に書かれていないことは書かない
   - 独自の解釈、推測、一般化は行わない
   - 必ず出典（[参照1]など）を明記

2. **詳細説明セクション**:
   - 各文や段落の最後に、その情報がどの参照から来ているかを（[参照1]）のように記載
   - 複数の参照から情報を得た場合は、（[参照1, 2]）のように記載
   - 法律条文、施行規則、FAQ それぞれの情報を区別して活用

3. **書式**:
   - Slack用に、箇条書きや段落を見やすく整形
   - 全く関連する情報がない場合は、「提供された情報には、この質問に対する回答が含まれていません」と答える

# コンテキスト情報
{context}

# 質問
{question}

# 回答（必ず上記の構成に従ってください）
"""

# Slack Appの初期化
app = App(token=SLACK_BOT_TOKEN)


# ベクトルDBとハイブリッド検索の初期化
def load_vectordb_with_hybrid_search():
    """ベクトルDBを読み込み、ハイブリッド検索retrieverを作成"""
    print("  [1/4] 埋め込みモデルを初期化中...")
    embedding_model = OpenAIEmbeddings(
        model="text-embedding-3-large",
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
        model="gemini-2.5-flash",
        google_api_key=GOOGLE_API_KEY,
        temperature=0.1,  # 厳格な判定のため低温度
    )
    
    # プロンプトの作成
    prompt = PromptTemplate.from_template(CLARITY_CHECK_PROMPT)
    
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
        model="gemini-2.5-flash",
        google_api_key=GOOGLE_API_KEY,
        temperature=0.1,
    )
    
    # 追加情報を整形
    additional_info_text = "\n".join([f"- {info}" for info in additional_info])
    
    # プロンプトの作成
    prompt = PromptTemplate.from_template(CLARITY_RECHECK_PROMPT)
    
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


def create_law_selection_blocks(question: str):
    """法律選択用のボタンブロックを作成"""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"📋 質問を受け付けました:\n> {question}\n\nどの法律に関する質問ですか？"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📜 景表法"},
                    "value": f"keihyouhou|||{question}",
                    "action_id": "select_law_keihyouhou"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "💰 資金決済法"},
                    "value": f"shikin_kessai|||{question}",
                    "action_id": "select_law_shikin_kessai"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔐 個人情報保護法"},
                    "value": f"kojin_jouhou|||{question}",
                    "action_id": "select_law_kojin_jouhou"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📝 印紙税法"},
                    "value": f"inshi_zei|||{question}",
                    "action_id": "select_law_inshi_zei"
                }
            ]
        }
    ]


def generate_answer_directly(query: str, hybrid_retriever, law_type: str = "景表法"):
    """質問の具体性チェックをスキップして直接回答を生成（追加情報統合後用）"""
    
    print(f"  [直接回答生成] 質問: {query}")
    
    # 1. 検索クエリを拡張（法律名を追加して精度向上）
    enhanced_query = f"{law_type} {query}"
    
    # 2. ハイブリッド検索を実行（多めに取得してフィルタリング）
    docs_and_scores = hybrid_retriever.search(enhanced_query, k=TOP_K_RESULTS * 3)
    
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
            "question": lambda x: query,  # 元のクエリを使用
            "law_type": lambda x: law_type
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    
    # 回答の生成
    answer = rag_chain.invoke(query)
    
    # 参照元情報の整形（Slack用）
    references = []
    for i, (doc, score) in enumerate(filtered_docs, 1):
        source = doc.metadata.get('source', '不明')
        
        # ファイル名を短縮
        if 'Q&A' in source:
            source_label = "FAQ"
        elif '施行規則' in source or '施行令' in source:
            source_label = "施行規則・施行令"
        elif '不当景品類及び不当表示防止法.pdf' in source:
            source_label = "📜 景表法"
        elif '資金決済に関する法律.pdf' in source:
            source_label = "💰 資金決済法"
        elif '個人情報の保護に関する法律' in source:
            source_label = "🔐 個人情報保護法"
        elif '印紙税法.pdf' in source:
            source_label = "📝 印紙税法"
        else:
            source_label = source
        
        hybrid_score = doc.metadata.get('hybrid_score', 0)
        references.append(f"[{i}] {source_label} (スコア: {hybrid_score:.3f})")
    
    return answer, references


def generate_answer(query: str, hybrid_retriever, law_type: str = "景表法"):
    """質問に対して回答を生成（法律タイプでフィルタリング・拡張）"""
    
    # ステップ1: 質問の具体性をチェック
    print(f"  [質問の具体性をチェック中...] 質問: {query}")
    clarity_result = check_question_clarity(query, law_type)
    
    # ステップ2: 質問が曖昧な場合は追加ヒアリング
    if not clarity_result.get("is_clear", True):
        print(f"  [判定] 質問が曖昧 - 追加ヒアリングを実施")
        
        missing_aspects = clarity_result.get("missing_aspects", [])
        clarifying_questions = clarity_result.get("clarifying_questions", [])
        
        # 追加ヒアリングのメッセージを生成
        clarification_message = f"❓ **質問を具体化させてください**\n\n"
        clarification_message += f"ご質問の内容をより正確に理解するために、以下の点について教えていただけますか？\n\n"
        
        for i, q in enumerate(clarifying_questions[:3], 1):
            clarification_message += f"{i}. {q}\n"
        
        clarification_message += f"\nより具体的な情報をいただければ、**{law_type}**の観点から適切な回答を提供できます。"
        
        # 追加ヒアリングの場合は参照なし
        return clarification_message, []
    
    # ステップ3: 質問が具体的な場合は回答を生成
    print(f"  [判定] 質問が具体的 - 回答を生成します")
    
    # 1. 検索クエリを拡張（法律名を追加して精度向上）
    enhanced_query = f"{law_type} {query}"
    
    # 2. ハイブリッド検索を実行（多めに取得してフィルタリング）
    docs_and_scores = hybrid_retriever.search(enhanced_query, k=TOP_K_RESULTS * 3)
    
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
            "question": lambda x: query,  # 元のクエリを使用
            "law_type": lambda x: law_type
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    
    # 回答の生成
    answer = rag_chain.invoke(query)
    
    # 参照元情報の整形（Slack用）
    references = []
    for i, (doc, score) in enumerate(filtered_docs, 1):
        source = doc.metadata.get('source', '不明')
        
        # ファイル名を短縮
        if 'Q&A' in source:
            source_label = "FAQ"
        elif '施行規則' in source or '施行令' in source:
            source_label = "施行規則・施行令"
        elif '不当景品類及び不当表示防止法.pdf' in source:
            source_label = "📜 景表法"
        elif '資金決済に関する法律.pdf' in source:
            source_label = "💰 資金決済法"
        elif '個人情報の保護に関する法律' in source:
            source_label = "🔐 個人情報保護法"
        elif '印紙税法.pdf' in source:
            source_label = "📝 印紙税法"
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
                
                # 回答を送信
                response_text = f"*📝 回答 ({law_type}):*\n{answer}\n\n*📚 参照元:*\n"
                for ref in references:
                    response_text += f"  • {ref}\n"
                
                say(response_text, thread_ts=thread_ts)
                
                # コンテキストをクリア
                del thread_contexts[thread_ts]
                print(f"  [スレッドコンテキスト削除] thread_ts={thread_ts}")
                
            else:
                # まだ不足している場合は追加質問
                still_missing = recheck_result.get('still_missing_aspects', [])
                next_questions = recheck_result.get('next_clarifying_questions', [])
                
                clarification_message = f"❓ **もう少し情報が必要です**\n\n"
                clarification_message += f"以下の点について教えていただけますか？\n\n"
                
                for i, q in enumerate(next_questions[:3], 1):
                    clarification_message += f"{i}. {q}\n"
                
                clarification_message += f"\n不足している情報: {', '.join(still_missing)}"
                
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
        
        # 回答を整形（Slack用）
        if references:
            response_text = f"*📝 回答 ({law_type}):*\n{answer}\n\n*📚 参照元:*\n"
            for ref in references:
                response_text += f"  • {ref}\n"
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
    
    # Socket Modeで起動
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()

