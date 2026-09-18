import json
from pathlib import Path

from .embed import Embedder, cosine

_emb = Embedder()  # bound at import to respect hash-by-default; swap via env


class VectorStore:
    """Flat, zero-dependency vector store with hybrid retrieval.

    Persisted as JSON so the demo runs with no external database.
    Swap for pgvector / qdrant / sqlite-vss by implementing the same
    two methods (add, search) — nothing else changes. Embeddings come
    from the pluggable Embedder (hash by default, OpenAI-compatible
    when keyed).
    """

    def __init__(self, embedder: Embedder | None = None) -> None:
        self.docs: list[dict] = []  # {id, text, vec, source}
        self._embedder = embedder or _emb

    def add(self, texts: list[str], source: str) -> int:
        before = len(self.docs)
        vectors = self._embedder.embed(texts)
        for text, vec in zip(texts, vectors):
            self.docs.append(
                {
                    "id": f"{source}:{len(self.docs)}",
                    "text": text,
                    "vec": vec,
                    "source": source,
                }
            )
        return len(self.docs) - before

    def search(self, query: str, k: int = 3, vector_weight: float = 0.6) -> list[dict]:
        if not self.docs:
            return []
        qv = self._embedder.embed([query])[0]
        q_terms = set(query.lower().split())
        scored: list[tuple[float, dict]] = []
        for doc in self.docs:
            vec_score = cosine(qv, doc["vec"])
            doc_terms = set(doc["text"].lower().split())
            overlap = len(q_terms & doc_terms) / max(1, len(q_terms))
            score = vector_weight * vec_score + (1 - vector_weight) * overlap
            scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "id": doc["id"],
                "text": doc["text"][:300],
                "source": doc["source"],
                "score": round(score, 4),
            }
            for score, doc in scored[:k]
        ]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {k: v for k, v in d.items() if k != "vec"} | {"vec": list(d["vec"])}
            for d in self.docs
        ]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    def load(self, path: Path) -> None:
        if not path.exists():
            return
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.docs = [{"vec": list(d.pop("vec")), **d} for d in payload]