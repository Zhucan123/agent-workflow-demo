import pytest

from app import config
from app.rag.embed import Embedder, cosine, hash_embed
from app.rag.ingest import chunk_text
from app.rag.store import VectorStore


def _load_docs():
    store = VectorStore()
    for f in sorted(config.DOCS_DIR.glob("*.md")):
        content = f.read_text(encoding="utf-8")
        store.add(chunk_text(content), f.name)
    return store


def test_chunking_respects_boundaries():
    text = "First sentence. " * 120
    chunks = chunk_text(text, size=300, overlap=30)
    assert len(chunks) > 1
    assert all(len(c) <= 300 + len("First sentence. ") for c in chunks)


def test_hash_embed_is_deterministic_and_normalized():
    a = hash_embed("refund policy within 14 days")
    b = hash_embed("refund policy within 14 days")
    c = hash_embed("shipping takes three to five days")
    assert a == b
    assert round(sum(v * v for v in a) ** 0.5, 6) == pytest.approx(1.0)
    assert cosine(a, c) < cosine(a, b)


def test_embedder_falls_back_to_hash_without_key():
    assert Embedder(backend="openai", api_key="").embed(["hello"])[0] == hash_embed(
        "hello"
    )


def test_embedder_unknown_backend_uses_hash():
    assert Embedder(backend="magic").embed(["x"])[0] == hash_embed("x")


def test_store_accepts_custom_embedder():
    custom = Embedder(backend="hash")
    store = VectorStore(embedder=custom)
    assert store.add(["a text", "another"], "docs.md") == 2
    assert len(store.docs[0]["vec"]) == 256


def test_hybrid_search_returns_relevant_first():
    store = _load_docs()
    hits = store.search("how long is the refund window", k=2)
    assert hits
    assert hits[0]["source"] == "refund-policy.md"