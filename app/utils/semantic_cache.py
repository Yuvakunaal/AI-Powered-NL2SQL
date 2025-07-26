import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import threading

class SemanticNL2SQLCache:
    def __init__(self, vector_dim=384, model_name="all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.vector_dim = vector_dim
        self.index = faiss.IndexFlatL2(vector_dim)
        self.cache = []  # Each is dict: {'nl_query','sql','result','explanation'}
        self.lock = threading.Lock()

    def embed(self, text):
        return np.array(self.model.encode([text])[0]).astype('float32')

    def add(self, nl_query, sql, result, explanation=None, explain_flag=False):
        vec = self.embed(self._cache_key(nl_query, explain_flag))
        with self.lock:
            self.index.add(np.array([vec]))
            self.cache.append({
                'nl_query': nl_query,
                'sql': sql,
                'result': result,
                'explanation': explanation,
                'explain_flag': explain_flag
            })


    def search(self, nl_query, explain_flag=False, threshold=0.87, k=3):
        if self.index.ntotal == 0:
            return None
        vec = self.embed(self._cache_key(nl_query, explain_flag))
        D, I = self.index.search(np.array([vec]), k)
        for dist, idx in zip(D[0], I[0]):
            if idx < 0: continue
            if self.cache[idx]['explain_flag'] != explain_flag:
                continue  # Only return cache entry with matching explanation preference
            similarity = 1 / (1 + dist)
            if similarity >= threshold:
                return self.cache[idx]
        return None

    def _cache_key(self, nl_query, explain_flag):
        # Make the explanation flag part of the semantic meaning.
        if explain_flag:
            return f"{nl_query} [EXPLAIN]"
        return nl_query

# Create a singleton cache for app-wide use
semantic_cache = SemanticNL2SQLCache()
