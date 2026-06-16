import numpy as np
import time
from loguru import logger
from fastembed import TextEmbedding

class SemanticRouter:
    """
    Singleton class that manages the FastEmbed ONNX model locally.
    It generates embeddings for all registered intent examples and computes cosine similarity
    to route user commands mathematically.
    """
    _instance = None
    _model = None
    _is_ready = False
    
    # Store tuples of (intent_name, embedding_vector, original_text)
    _intent_embeddings: list[tuple[str, np.ndarray, str]] = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SemanticRouter, cls).__new__(cls)
        return cls._instance

    def initialize(self, intents: list):
        """Loads the embedding model and pre-computes embeddings for all intents."""
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
                
                for i, emb in enumerate(embeddings):
                    self._intent_embeddings.append((mapping[i], emb, texts_to_embed[i]))
                    
            self._is_ready = True
            logger.info(f"Semantic Router initialized in {(time.perf_counter() - start) * 1000:.2f}ms")
        except Exception as e:
            logger.error(f"Failed to initialize Semantic Router: {e}")

    def semantic_match(self, text: str, threshold: float = 0.82) -> tuple[str | None, float]:
        """
        Embeds the input text and finds the closest matching intent using cosine similarity.
        Returns a tuple of (intent_name, similarity_score).
        """
        if not self._is_ready or not self._intent_embeddings:
            return None, 0.0

        try:
            # FastEmbed returns a generator, so we wrap in list and take the first item
            query_emb = list(self._model.embed([text]))[0]
            
            best_match = None
            highest_sim = -1.0
            
            query_norm = np.linalg.norm(query_emb)
            if query_norm == 0:
                return None, 0.0

            for intent_name, doc_emb, ex_text in self._intent_embeddings:
                doc_norm = np.linalg.norm(doc_emb)
                if doc_norm == 0:
                    continue
                
                # Cosine Similarity = dot_product / (norm(a) * norm(b))
                sim = np.dot(query_emb, doc_emb) / (query_norm * doc_norm)
                
                if sim > highest_sim:
                    highest_sim = sim
                    best_match = intent_name
                    
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
