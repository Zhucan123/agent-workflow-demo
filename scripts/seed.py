#!/usr/bin/env python3
"""Seed the RAG corpus: chunk the docs under data/docs and persist the store.

Usage (from server/):  uv run python ../scripts/seed.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from app import config
from app.rag.ingest import chunk_text, read_docs
from app.rag.store import VectorStore

config.ensure_dirs()
store = VectorStore()

docs = read_docs(config.DOCS_DIR)
if not docs:
    print("No .md/.txt docs found under", config.DOCS_DIR)
    sys.exit(1)
for source, content in docs:
    added = store.add(chunk_text(content), source)
    print(f"  +{added:<3} chunks  {source}")
store.save(config.VSTORE_PATH)
print(f"Done. {len(store.docs)} chunks persisted at {config.VSTORE_PATH}")