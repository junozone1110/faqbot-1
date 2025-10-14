#!/usr/bin/env python3
"""
ハイブリッド検索（BM25 + ベクトル検索）の実装
キーワード検索とセマンティック検索を組み合わせて、より精度の高い検索を実現
"""

from typing import List, Tuple
from rank_bm25 import BM25Okapi
import numpy as np
from langchain_community.vectorstores import Chroma


class HybridSearchRetriever:
    """
    BM25（キーワード検索）とベクトル検索を組み合わせたハイブリッド検索
    
    Parameters:
    -----------
    vectordb : Chroma
        LangChainのChromaベクトルデータベース
    alpha : float (default: 0.5)
        ベクトル検索の重み（0.0-1.0）
        - 1.0: 完全にベクトル検索のみ
        - 0.5: BM25とベクトル検索を同じ重み
        - 0.0: 完全にBM25のみ
    """
    
    def __init__(self, vectordb: Chroma, alpha: float = 0.5):
        self.vectordb = vectordb
        self.alpha = alpha  # ベクトル検索の重み
        self.bm25_weight = 1.0 - alpha  # BM25の重み
        
        # ベクトルDBから全ドキュメントを取得
        print("     - 全ドキュメントを取得中...")
        self.all_data = vectordb.get()
        self.documents = self.all_data['documents']
        self.metadatas = self.all_data['metadatas']
        print(f"     - 取得完了: {len(self.documents)}件のドキュメント")
        
        # BM25用にトークン化（簡易的に文字単位で分割）
        print("     - ドキュメントをトークン化中...")
        self.tokenized_corpus = [self._tokenize(doc) for doc in self.documents]
        print("     - トークン化完了")
        
        # BM25インデックスを構築
        print("     - BM25インデックスを構築中...")
        self.bm25 = BM25Okapi(self.tokenized_corpus)
        print("     - BM25インデックス構築完了")
        
        print(f"     ✓ ハイブリッド検索の初期化完了:")
        print(f"       - ドキュメント数: {len(self.documents)}")
        print(f"       - ベクトル検索の重み: {self.alpha:.2f}")
        print(f"       - BM25の重み: {self.bm25_weight:.2f}")
    
    def _tokenize(self, text: str) -> List[str]:
        """
        テキストをトークン化
        日本語の場合、文字レベルとバイグラムで分割
        """
        # 文字レベル
        chars = list(text)
        
        # バイグラム（2文字の組み合わせ）
        bigrams = [text[i:i+2] for i in range(len(text)-1)]
        
        # トライグラム（3文字の組み合わせ）
        trigrams = [text[i:i+3] for i in range(len(text)-2)]
        
        return chars + bigrams + trigrams
    
    def _normalize_scores(self, scores: List[float]) -> np.ndarray:
        """
        スコアを0-1の範囲に正規化（Min-Max正規化）
        """
        scores_array = np.array(scores)
        
        if len(scores_array) == 0:
            return scores_array
        
        min_score = scores_array.min()
        max_score = scores_array.max()
        
        if max_score == min_score:
            # 全て同じスコアの場合
            return np.ones_like(scores_array)
        
        normalized = (scores_array - min_score) / (max_score - min_score)
        return normalized
    
    def search(self, query: str, k: int = 5) -> List[Tuple[any, float]]:
        """
        ハイブリッド検索を実行
        
        Parameters:
        -----------
        query : str
            検索クエリ
        k : int
            返す結果の数
            
        Returns:
        --------
        List[Tuple[Document, float]]
            (ドキュメント, スコア)のリスト（スコアが高い順）
        """
        # 1. BM25検索
        tokenized_query = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(tokenized_query)
        
        # 2. ベクトル検索（全ドキュメントに対するスコアを取得）
        # ChromaDBはデフォルトで距離を返すため、より多くの結果を取得
        vector_results = self.vectordb.similarity_search_with_score(
            query, 
            k=len(self.documents)
        )
        
        # ベクトル検索の結果をインデックスとスコアのマップに変換
        # 距離を類似度に変換（距離が小さいほど類似度が高い）
        vector_scores_dict = {}
        for doc, distance in vector_results:
            # ドキュメントのインデックスを見つける
            try:
                idx = self.documents.index(doc.page_content)
                # 距離を類似度に変換（負の距離にする）
                vector_scores_dict[idx] = -distance
            except ValueError:
                continue
        
        # 全ドキュメント分のベクトルスコアを配列に変換
        vector_scores = np.array([
            vector_scores_dict.get(i, -1000.0)  # 見つからない場合は非常に低いスコア
            for i in range(len(self.documents))
        ])
        
        # 3. スコアの正規化
        bm25_scores_norm = self._normalize_scores(bm25_scores)
        vector_scores_norm = self._normalize_scores(vector_scores)
        
        # 4. ハイブリッドスコアの計算（重み付き平均）
        hybrid_scores = (
            self.bm25_weight * bm25_scores_norm + 
            self.alpha * vector_scores_norm
        )
        
        # 5. 上位k件を取得
        top_indices = np.argsort(hybrid_scores)[::-1][:k]
        
        # 6. 結果を構築
        results = []
        for idx in top_indices:
            # LangChainのDocumentオブジェクトを作成
            from langchain_core.documents import Document
            doc = Document(
                page_content=self.documents[idx],
                metadata=self.metadatas[idx]
            )
            score = hybrid_scores[idx]
            
            # スコアの詳細を追加
            doc.metadata['hybrid_score'] = float(score)
            doc.metadata['bm25_score'] = float(bm25_scores_norm[idx])
            doc.metadata['vector_score'] = float(vector_scores_norm[idx])
            
            results.append((doc, score))
        
        return results
    
    def search_multi_source(self, query: str, k_per_source: int = 2) -> List[Tuple[any, float]]:
        """
        マルチソース検索：各ファイルから上位k_per_source件ずつ取得
        
        これにより、FAQだけでなく法律条文も必ず結果に含まれるようにする
        
        Parameters:
        -----------
        query : str
            検索クエリ
        k_per_source : int
            各ファイルから取得する結果の数
            
        Returns:
        --------
        List[Tuple[Document, float]]
            (ドキュメント, スコア)のリスト（ファイルごとにグループ化）
        """
        # まず全体で検索
        all_results = self.search(query, k=len(self.documents))
        
        # ソースごとにグループ化
        from collections import defaultdict
        results_by_source = defaultdict(list)
        
        for doc, score in all_results:
            source = doc.metadata.get('source', '不明')
            results_by_source[source].append((doc, score))
        
        # 各ソースから上位k_per_source件を取得
        final_results = []
        for source in sorted(results_by_source.keys()):
            top_results = results_by_source[source][:k_per_source]
            final_results.extend(top_results)
        
        return final_results
    
    def search_with_score_details(self, query: str, k: int = 5) -> List[dict]:
        """
        スコアの詳細情報を含む検索結果を返す（デバッグ用）
        
        Returns:
        --------
        List[dict]
            各結果の詳細情報
        """
        results = self.search(query, k)
        
        detailed_results = []
        for doc, hybrid_score in results:
            detailed_results.append({
                'content': doc.page_content[:200] + '...',
                'source': doc.metadata.get('source', '不明'),
                'chunk_id': doc.metadata.get('chunk_id', '不明'),
                'hybrid_score': doc.metadata.get('hybrid_score', 0.0),
                'bm25_score': doc.metadata.get('bm25_score', 0.0),
                'vector_score': doc.metadata.get('vector_score', 0.0),
            })
        
        return detailed_results


def demo():
    """
    デモ用の簡単な使用例
    """
    from langchain_openai import OpenAIEmbeddings
    from dotenv import load_dotenv
    import os
    
    load_dotenv()
    
    CHROMA_DB_DIR = "./chroma_db_openai"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    if not OPENAI_API_KEY:
        print("エラー: OPENAI_API_KEYが設定されていません")
        return
    
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
    
    # ハイブリッド検索の初期化
    hybrid_retriever = HybridSearchRetriever(
        vectordb=vectordb,
        alpha=0.5  # BM25とベクトル検索を同じ重みで
    )
    
    # テスト検索
    query = "景品類の定義を教えて"
    print(f"\n検索クエリ: {query}\n")
    print("=" * 100)
    
    results = hybrid_retriever.search_with_score_details(query, k=10)
    
    for i, result in enumerate(results, 1):
        print(f"\n[{i}] ハイブリッドスコア: {result['hybrid_score']:.4f}")
        print(f"    - BM25: {result['bm25_score']:.4f}, ベクトル: {result['vector_score']:.4f}")
        print(f"    - 出典: {result['source']}")
        print(f"    - 内容: {result['content']}")


if __name__ == "__main__":
    demo()

