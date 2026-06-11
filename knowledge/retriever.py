import os
import json
import numpy as np
from config import INDEX_PATH, TIERS, CORPUS_PATH


class KnowledgeRetriever:
    def __init__(self):
        self._index = None
        self._chunks = None
        self._model = None
        self._bm25 = None
        self._use_dense = False
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        self._loaded = True

        index_file = os.path.join(INDEX_PATH, "coach.index")
        chunks_file = os.path.join(INDEX_PATH, "chunks.json")

        if os.path.exists(chunks_file):
            with open(chunks_file, "r", encoding="utf-8") as f:
                self._chunks = json.load(f)
        else:
            from knowledge.embeddings import load_and_chunk_corpus
            self._chunks = load_and_chunk_corpus()
            os.makedirs(INDEX_PATH, exist_ok=True)
            with open(chunks_file, "w", encoding="utf-8") as f:
                json.dump(self._chunks, f, indent=2)

        from rank_bm25 import BM25Okapi
        tokenized = [c["content"].lower().split() for c in self._chunks]
        self._bm25 = BM25Okapi(tokenized)

        if os.path.exists(index_file):
            try:
                import faiss
                from sentence_transformers import SentenceTransformer
                self._index = faiss.read_index(index_file)
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
                self._use_dense = True
            except Exception:
                self._use_dense = False
        else:
            self._use_dense = False

    def retrieve(self, query: str, tier: str = "general", top_k: int = 3, coach: str | None = None) -> list[dict]:
        """Hybrid retrieval when FAISS available, BM25-only fallback otherwise."""
        self._load()

        # Cross-cutting corpora (psychology, mentality, tactics, planning) apply
        # to every runner, so they are always treated as tier-relevant. The
        # active coach's own brain (coach_<style>) is boosted when present.
        tier_relevant = {"general", "psychology", "mentality", "tactics", "planning", tier}
        if coach:
            tier_relevant.add(f"coach_{coach}")
        max_chunks = TIERS.get(tier, {}).get("max_rag_chunks", 3)

        bm25_scores = self._bm25.get_scores(query.lower().split())

        scored_results = []
        seen_ids = set()

        if self._use_dense and self._index is not None:
            query_embedding = self._model.encode([query], normalize_embeddings=True)
            dense_scores, dense_indices = self._index.search(
                np.array(query_embedding).astype("float32"), top_k * 3
            )

            for i, idx in enumerate(dense_indices[0]):
                if idx < 0 or idx >= len(self._chunks):
                    continue
                chunk = self._chunks[idx]
                if chunk["id"] in seen_ids:
                    continue
                seen_ids.add(chunk["id"])

                dense_score = float(dense_scores[0][i])
                sparse_score = float(bm25_scores[idx]) if idx < len(bm25_scores) else 0
                tier_boost = 1.3 if chunk["tier_tag"] in tier_relevant else 0.7
                combined = (dense_score * 0.7 + sparse_score * 0.01) * tier_boost

                scored_results.append({
                    "chunk": chunk,
                    "score": combined,
                    "dense_score": dense_score,
                    "sparse_score": sparse_score,
                })

        bm25_top = np.argsort(bm25_scores)[-top_k * 3:][::-1]
        for idx in bm25_top:
            if idx >= len(self._chunks):
                continue
            chunk = self._chunks[idx]
            if chunk["id"] in seen_ids:
                continue
            seen_ids.add(chunk["id"])

            sparse_score = float(bm25_scores[idx])
            tier_boost = 1.3 if chunk["tier_tag"] in tier_relevant else 0.7
            combined = sparse_score * 0.02 * tier_boost

            scored_results.append({
                "chunk": chunk,
                "score": combined,
                "dense_score": 0,
                "sparse_score": sparse_score,
            })

        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return scored_results[:max_chunks]


retriever = KnowledgeRetriever()
