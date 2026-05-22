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
        # Each session gets its own isolated collection
        return self.client.get_or_create_collection(
            name=f"session_{session_id}",
            metadata={"created": str(datetime.now())}
        )

    def write(self, session_id: str, fact: str) -> dict:
        collection = self._get_collection(session_id)

        # Auto-summarise if too many facts
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
            n_results=min(top_k, collection.count())
        )

        facts = results["documents"][0]
        return {
            "question": question,
            "results":  facts,
            "count":    len(facts)
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
        # Keep only the 25 most recent facts when limit is hit
        collection = self._get_collection(session_id)
        all_data = collection.get()
        ids = all_data["ids"]
        old_ids = ids[:len(ids) // 2]  # remove oldest half
        collection.delete(ids=old_ids)


if __name__ == "__main__":
    memory = MemoryStore()
    SESSION = "test_session_1"

    # Clean start
    memory.clear(SESSION)

    print("--- MemoryStore Test ---\n")

    # Agent 1 writes facts
    print("Agent 1 writing facts...")
    memory.write(SESSION, "The user's name is Neeraj")
    memory.write(SESSION, "The user wants a refund for order #4521")
    memory.write(SESSION, "The user is a premium subscriber since 2023")
    memory.write(SESSION, "The user prefers communication in Hindi")

    # Agent 2 queries memory in natural language
    print("\nAgent 2 querying memory...\n")

    queries = [
        "What does the user want?",
        "What is the user's name?",
        "What language does the user prefer?",
    ]

    for question in queries:
        result = memory.query(SESSION, question, top_k=2)
        print(f"Q: {question}")
        for fact in result["results"]:
            print(f"   → {fact}")
        print()

    # List all facts
    all_facts = memory.list_facts(SESSION)
    print(f"Total facts stored: {all_facts['fact_count']}")
    for f in all_facts["facts"]:
        print(f"  • {f}")