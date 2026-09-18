import re
from pathlib import Path

CHUNK_SIZE = 512
CHUNK_OVERLAP = 64


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Sentence-aware chunking: prefer breaking at sentence boundaries."""
    normalized = text.replace("\x00", "").strip()
    if not normalized:
        return []
    sentences = re.split(r"(?<=[.!?。])\s+", normalized)
    chunks: list[str] = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) + 1 > size and current:
            chunks.append(current.strip())
            current = current[-overlap:] if len(current) > overlap else ""
        current += (" " if current else "") + sent
    if current.strip():
        chunks.append(current.strip())
    return chunks


def read_docs(docs_dir: Path) -> list[tuple[str, str]]:
    """Returns [(source, content)] for .md and .txt files."""
    results: list[tuple[str, str]] = []
    for f in sorted(docs_dir.glob("*.*")):
        if f.suffix.lower() not in (".md", ".txt"):
            continue
        if f.name.startswith("."):
            continue
        results.append((f.name, f.read_text(encoding="utf-8", errors="replace")))
    return results