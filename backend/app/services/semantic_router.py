import numpy as np
import time
from loguru import logger
from fastembed import TextEmbedding

class SemanticRouter:
    """
    Singleton class that manages the FastEmbed ONNX model locally.
    It generates embeddings for all registered intent examples and computes cosine similarity
    to route user commands mathematically.

    Optimizations vs v1:
      - Document embeddings are pre-normalized to unit-vectors at init time, so
        semantic_match() only needs 1 norm (the query) and N dot-products instead
        of N+1 norms + N divisions on every call.
      - All N cosine similarities are computed with a single np.matmul (vectorized
        BLAS call) instead of a Python for-loop — ~10× faster on large intent sets.
    """
    _instance = None
    _model = None
    _is_ready = False

    # Store tuples of (intent_name, unit_embedding, original_text)
    _intent_embeddings: list[tuple[str, np.ndarray, str]] = []
    # Stacked matrix of all unit-embeddings — shape (N, dim)
    _doc_matrix: np.ndarray | None = None
    _doc_names: list[str] = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SemanticRouter, cls).__new__(cls)
        return cls._instance

    def initialize(self, intents: list):
        """Loads the embedding model and pre-computes normalized embeddings for all intents."""
        if self._is_ready:
            return

        logger.info("Initializing FastEmbed Semantic Router... (this may take a moment on first run to download model)")
        start = time.perf_counter()
        try:
            import os
            # Use a stable cache directory to prevent third-party temp folder corruption (e.g. Wondershare)
            cache_dir = os.path.join(os.getenv("LOCALAPPDATA", os.path.expanduser("~")), "ACEVoiceController", "models", "fastembed")
            os.makedirs(cache_dir, exist_ok=True)
            
            # BAAI/bge-small-en-v1.5 is a very fast, highly accurate embedding model (~130MB)
            self._model = TextEmbedding("BAAI/bge-small-en-v1.5", threads=4, cache_dir=cache_dir)
            
            # Prepare data to embed
            self._intent_embeddings.clear()
            texts_to_embed = []
            mapping = []
            
            for intent in intents:
                if intent.examples:
                    for ex in intent.examples:
                        texts_to_embed.append(ex)
                        mapping.append(intent.name)
            
            if texts_to_embed:
                logger.info(f"Computing embeddings for {len(texts_to_embed)} intent examples...")
                embeddings = list(self._model.embed(texts_to_embed))
                
                # ── Pre-normalize all document embeddings once ────────────────
                # Storing unit-vectors means semantic_match() only needs 1 norm
                # (the query) and N pure dot-products, not N+1 norms + N divisions.
                for i, emb in enumerate(embeddings):
                    norm = np.linalg.norm(emb)
                    normalized = emb / norm if norm > 0 else emb.copy()
                    self._intent_embeddings.append((mapping[i], normalized, texts_to_embed[i]))
                    
                # ── Build a stacked matrix for vectorized matching ────────────
                # Shape: (num_examples, embedding_dim)
                # Enables a single np.matmul call instead of a Python loop.
                self._doc_matrix = np.stack([emb for _, emb, _ in self._intent_embeddings])
                self._doc_names  = [name for name, _, _ in self._intent_embeddings]
                    
            self._is_ready = True
            logger.info(f"✅ Semantic Router initialized in {(time.perf_counter() - start) * 1000:.2f}ms "
                        f"({len(texts_to_embed)} examples, vectorized matching enabled)")
        except Exception as e:
            logger.error(f"Failed to initialize Semantic Router: {e}")

    def semantic_match(self, text: str, threshold: float = 0.82) -> tuple[str | None, float]:
        """
        Embeds the input text and finds the closest matching intent using cosine similarity.
        Returns a tuple of (intent_name, similarity_score).

        Optimization: document embeddings are pre-normalized at init time, so only the
        query vector needs normalizing here. Cosine similarity is computed via a single
        np.matmul BLAS call (vectorized) — O(N) with no Python loop.
        """
        if not self._is_ready or not self._intent_embeddings or self._doc_matrix is None:
            return None, 0.0

        try:
            # FastEmbed returns a generator — wrap in list and take first item
            query_emb = list(self._model.embed([text]))[0]
            
            query_norm = np.linalg.norm(query_emb)
            if query_norm == 0:
                return None, 0.0

            # Normalize query to unit vector (only 1 norm needed per call)
            query_normalized = query_emb / query_norm

            # ── Vectorized cosine similarity via matrix-vector multiply ───────
            # doc_matrix rows are pre-normalized unit-vectors, so:
            #   cosine(q, d_i) = dot(q_unit, d_unit_i)
            # np.matmul computes all N dot-products in one BLAS call — no Python loop
            similarities = np.matmul(self._doc_matrix, query_normalized)  # shape: (N,)
            
            best_idx     = int(np.argmax(similarities))
            highest_sim  = float(similarities[best_idx])
            best_match   = self._doc_names[best_idx]
                
            if highest_sim >= threshold:
                logger.info(f"[Semantic] Matched '{text}' -> {best_match} (score: {highest_sim:.3f})")
                return best_match, highest_sim
            else:
                logger.debug(f"[Semantic] No match for '{text}'. Best was {best_match} ({highest_sim:.3f}) < {threshold}")
                return None, highest_sim
                
        except Exception as e:
            logger.error(f"Semantic match failed: {e}")
            return None, 0.0

semantic_router = SemanticRouter()
