import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    print("ChromaDB not found. Using in-memory fallback.")

class VectorStore:
    def __init__(self, collection_name="resumes"):
        global CHROMA_AVAILABLE
        self.collection_name = collection_name
        self.client = None
        self.collection = None
        self.in_memory_vectors = {} # {id: vector}
        self.in_memory_docs = {}    # {id: document}
        
        if CHROMA_AVAILABLE:
            try:
                self.client = chromadb.Client(Settings(allow_reset=True))
                self.collection = self.client.get_or_create_collection(name=collection_name)
            except Exception as e:
                print(f"ChromaDB initialization failed: {e}. Switching to fallback.")
                CHROMA_AVAILABLE = False

    def add_documents(self, ids, documents, embeddings, metadatas=None):
        if CHROMA_AVAILABLE and self.collection:
            self.collection.add(
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )
        else:
            # Fallback
            for i, doc_id in enumerate(ids):
                self.in_memory_vectors[doc_id] = np.array(embeddings[i])
                self.in_memory_docs[doc_id] = documents[i]

    def query(self, query_embedding, n_results=5):
        if CHROMA_AVAILABLE and self.collection:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            return {
                "ids": results['ids'][0],
                "distances": results['distances'][0],
                "documents": results['documents'][0]
            }
        else:
            # Fallback: Scikit-Learn Cosine Similarity
            ids = list(self.in_memory_vectors.keys())
            if not ids:
                return {"ids": [], "distances": [], "documents": []}
                
            vectors = np.array(list(self.in_memory_vectors.values()))
            query_vec = np.array([query_embedding])
            
            # Calculate cosine similarity matrix (1xN)
            # Returns values between -1 and 1 (1 is identical)
            sims = cosine_similarity(query_vec, vectors)[0]
            
            # Convert to "distance" (1 - sim) for consistency with Chroma
            # Using 1 - sim is standard for cosine distance
            dists = 1 - sims
            
            # Sort
            sorted_indices = np.argsort(dists)
            top_indices = sorted_indices[:n_results]
            
            return {
                "ids": [ids[i] for i in top_indices],
                "distances": [dists[i] for i in top_indices],
                "documents": [self.in_memory_docs[ids[i]] for i in top_indices]
            }
