import asyncio
import hashlib


def _ngrams(text: str, n: int = 3) -> list[str]:
    tokens = [
        t for t in text.lower().replace("\n", " ").split() if t.strip()
    ]
    grams: list[str] = []
    for t in tokens:
        grams.append(t)
        if len(t) >= n:
            for i in range(len(t) - n + 1):
                grams.append(t[i : i + n])
    return grams


def hash_embed(text: str, dim: int = 256) -> list[float]:
    """Deterministic signed-hash embedding. No API key required,
    good enough to demonstrate hybrid retrieval."""
    vec = [0.0] * dim
    for gram in _ngrams(text):
        h = hashlib.md5(gram.encode("utf-8")).digest()
        idx = int.from_bytes(h[:4], "big") % dim
        sign = 1.0 if h[4] & 1 else -1.0
        vec[idx] += sign
    norm = sum(v * v for v in vec) ** 0.5
    if norm == 0:
        return vec
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class Embedder:
    """Pluggable embedder: `hash` (offline, deterministic, zero-dependency)
    or `openai` (any OpenAI-compatible /embeddings endpoint).

    Unknown backends or missing keys fall back to `hash`, so the demo
    always works — on CI, on laptops, without any API key.
    """

    def __init__(
        self,
        backend: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        from .. import config  # deferred import: avoid circularity

        self.backend = backend or config.EMBED_BACKEND
        self.base_url = base_url or config.OPENAI_BASE_URL
        self.api_key = str(api_key if api_key is not None else config.OPENAI_API_KEY)
        self.model = model or config.EMBED_MODEL
        self._openai_usable = self.backend == "openai" and self.api_key

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._openai_usable:
            try:
                return self._openai_embed(texts)
            except Exception:  # noqa: BLE001 - degrade gracefully on failures
                pass
        return [hash_embed(t) for t in texts]

    def _openai_embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        url = self.base_url.rstrip("/") + "/embeddings"
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                url,
                json={"model": self.model, "input": texts},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
        data = sorted(resp.json()["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in data]