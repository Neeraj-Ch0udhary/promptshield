import chromadb
from sentence_transformers import SentenceTransformer
from datetime import datetime
import uuid


class MemoryStore:
    def __init__(
        self,
        db_path: str = "./memory_db",
        model_name: str = "all-MiniLM-L6-v2",
        max_facts: int = 50,
    ):
        self.model = SentenceTransformer(model_name)
        self.client = chromadb.PersistentClient(path=db_path)
        self.max_facts = max_facts

    def _get_collection(self, session_id: str):
        return self.client.get_or_create_collection(
            name=f"session_{session_id}",
            metadata={"created": str(datetime.now())}
        )

    def write(self, session_id: str, fact: str) -> dict:
        collection = self._get_collection(session_id)
        if collection.count() >= self.max_facts:
            self._summarise(session_id)
        fact_id = str(uuid.uuid4())
        embedding = self.model.encode(fact).tolist()
        collection.add(
            ids=[fact_id],
            embeddings=[embedding],
            documents=[fact],
            metadatas=[{"timestamp": str(datetime.now())}]
        )
        return {"written": True, "fact_id": fact_id, "fact": fact}

    def query(self, session_id: str, question: str, top_k: int = 3) -> dict:
        collection = self._get_collection(session_id)
        if collection.count() == 0:
            return {"results": [], "question": question}
        embedding = self.model.encode(question).tolist()
        results = collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, collection.count()),
            include=["documents", "distances"]
        )
        docs = results["documents"][0]
        distances = results["distances"][0]
        filtered = [
            doc for doc, dist in zip(docs, distances)
            if dist < 1.5
        ]
        return {
            "question": question,
            "results":  filtered if filtered else docs,
            "count":    len(filtered)
        }

    def clear(self, session_id: str) -> dict:
        try:
            self.client.delete_collection(f"session_{session_id}")
            return {"cleared": True, "session_id": session_id}
        except Exception:
            return {"cleared": False, "session_id": session_id}

    def list_facts(self, session_id: str) -> dict:
        collection = self._get_collection(session_id)
        all_facts = collection.get()
        return {
            "session_id": session_id,
            "fact_count": collection.count(),
            "facts":      all_facts["documents"]
        }

    def _summarise(self, session_id: str):
        collection = self._get_collection(session_id)
        all_data = collection.get()
        ids = all_data["ids"]
        old_ids = ids[:len(ids) // 2]
        collection.delete(ids=old_ids)