"""
FAQ Bot ユーティリティ関数

このファイルには、アプリケーション全体で使用される共通関数を定義します。
- プロンプト読み込み
- 参照元整形
- メッセージ整形
"""

import os
from typing import List, Tuple
from config import (
    CLARITY_CHECK_PROMPT_FILE,
    CLARITY_RECHECK_PROMPT_FILE,
    ANSWER_GENERATION_PROMPT_FILE
)


def load_prompt(file_path: str) -> str:
    """
    プロンプトファイルを読み込む
    
    Args:
        file_path: プロンプトファイルのパス
        
    Returns:
        プロンプト文字列
        
    Raises:
        FileNotFoundError: ファイルが見つからない場合
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"プロンプトファイルが見つかりません: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def get_clarity_check_prompt() -> str:
    """質問の具体性チェック用プロンプトを取得"""
    return load_prompt(CLARITY_CHECK_PROMPT_FILE)


def get_clarity_recheck_prompt() -> str:
    """質問の再評価用プロンプトを取得"""
    return load_prompt(CLARITY_RECHECK_PROMPT_FILE)


def get_answer_generation_prompt() -> str:
    """回答生成用プロンプトを取得"""
    return load_prompt(ANSWER_GENERATION_PROMPT_FILE)


def format_source_label(source: str) -> str:
    """
    ソースファイル名を短縮表示用のラベルに変換
    
    Args:
        source: ソースファイル名
        
    Returns:
        短縮されたラベル
    """
    if 'Q&A' in source:
        return "FAQ"
    elif '施行規則' in source or '施行令' in source:
        return "施行規則・施行令"
    elif '不当景品類及び不当表示防止法.pdf' in source:
        return "📜 景表法"
    elif '資金決済に関する法律.pdf' in source:
        return "💰 資金決済法"
    elif '個人情報の保護に関する法律' in source:
        return "🔐 個人情報保護法"
    elif '印紙税法.pdf' in source:
        return "📝 印紙税法"
    else:
        return source


def format_references(filtered_docs: List[Tuple]) -> List[str]:
    """
    検索結果から参照元情報を整形
    
    Args:
        filtered_docs: (document, score)のタプルのリスト
        
    Returns:
        整形された参照元情報のリスト
    """
    references = []
    for i, (doc, score) in enumerate(filtered_docs, 1):
        source = doc.metadata.get('source', '不明')
        source_label = format_source_label(source)
        hybrid_score = doc.metadata.get('hybrid_score', score)
        references.append(f"[{i}] {source_label} (スコア: {hybrid_score:.3f})")
    
    return references


def format_docs(docs: List) -> str:
    """
    ドキュメントをフォーマットして、参照番号を付与
    
    Args:
        docs: ドキュメントのリスト
        
    Returns:
        フォーマットされたコンテキスト文字列
    """
    context_parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get('source', '不明')
        chunk_id = doc.metadata.get('chunk_id', '不明')
        
        # ファイル名を短縮
        source_type = format_source_label(source)
        
        context_parts.append(
            f"[参照{i}] (出典: {source_type}, {source}, ID: {chunk_id})\n{doc.page_content}\n"
        )
    
    return "\n".join(context_parts)


def create_clarification_message(
    clarifying_questions: List[str],
    law_type: str,
    max_questions: int = 3
) -> str:
    """
    追加ヒアリング用のメッセージを生成
    
    Args:
        clarifying_questions: 追加質問のリスト
        law_type: 法律の種類
        max_questions: 表示する質問の最大数
        
    Returns:
        整形されたメッセージ
    """
    message = "❓ **質問を具体化させてください**\n\n"
    message += "ご質問の内容をより正確に理解するために、以下の点について教えていただけますか？\n\n"
    
    for i, q in enumerate(clarifying_questions[:max_questions], 1):
        message += f"{i}. {q}\n"
    
    message += f"\nより具体的な情報をいただければ、**{law_type}**の観点から適切な回答を提供できます。"
    
    return message


def create_further_clarification_message(
    still_missing_aspects: List[str],
    next_clarifying_questions: List[str],
    max_questions: int = 3
) -> str:
    """
    さらなる追加ヒアリング用のメッセージを生成
    
    Args:
        still_missing_aspects: まだ不足している観点のリスト
        next_clarifying_questions: 次の追加質問のリスト
        max_questions: 表示する質問の最大数
        
    Returns:
        整形されたメッセージ
    """
    message = "❓ **もう少し情報が必要です**\n\n"
    message += "以下の点について教えていただけますか？\n\n"
    
    for i, q in enumerate(next_clarifying_questions[:max_questions], 1):
        message += f"{i}. {q}\n"
    
    message += f"\n不足している情報: {', '.join(still_missing_aspects)}"
    
    return message


def format_response_with_references(answer: str, references: List[str], law_type: str) -> str:
    """
    回答と参照元を整形してSlack用のメッセージを生成
    
    Args:
        answer: 回答テキスト
        references: 参照元のリスト
        law_type: 法律の種類
        
    Returns:
        整形されたメッセージ
    """
    if references:
        response_text = f"*📝 回答 ({law_type}):*\n{answer}\n\n*📚 参照元:*\n"
        for ref in references:
            response_text += f"  • {ref}\n"
    else:
        # 追加質問の場合はそのまま
        response_text = answer
    
    return response_text

