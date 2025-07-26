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

    def add(self, nl_query, sql, result, explanation=None):
        vec = self.embed(nl_query)
        with self.lock:
            self.index.add(np.array([vec]))
            self.cache.append({
                'nl_query': nl_query,
                'sql': sql,
                'result': result,
                'explanation': explanation,
            })

    def search(self, nl_query, threshold=0.87, k=3):
        if self.index.ntotal == 0:
            return None
        vec = self.embed(nl_query)
        D, I = self.index.search(np.array([vec]), k)
        for dist, idx in zip(D[0], I[0]):
            if idx < 0:
                continue
            similarity = 1 / (1 + dist)
            if similarity >= threshold:
                return self.cache[idx]
        return None

# Singleton
semantic_cache = SemanticNL2SQLCache()
