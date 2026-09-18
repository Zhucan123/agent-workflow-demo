from .store import VectorStore


class Retriever:
    """Hybrid retrieval facade used by the agent pipeline."""

    def __init__(self, store: VectorStore) -> None:
        self.store = store

    def search(self, query: str, k: int = 3) -> list[dict]:
        if not query.strip():
            return []
        return self.store.search(query, k=k)