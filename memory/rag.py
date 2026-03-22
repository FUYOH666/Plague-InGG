"""
RAG memory: embed, index, retrieve via Embedding Service.
Falls back to [] when API unavailable.
"""

import json
import logging
import os
import re
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
MEMORY_FILE = ROOT / "memory" / "stream.md"
VECTORS_FILE = ROOT / "memory" / "vectors.jsonl"
INDEX_MTIME_FILE = ROOT / "memory" / ".index_mtime"

CHUNK_MIN = 200
CHUNK_MAX = 500
TOP_K = 5


def _embed_url() -> str:
    base = os.getenv("LOCAL_AI_EMBEDDING_BASE_URL", "").strip()
    if not base:
        return ""
    return f"{base.rstrip('/')}/v1/embeddings"


def _timeout() -> float:
    return float(os.getenv("LOCAL_AI_EMBEDDING_TIMEOUT", "30"))


def embed(text: str) -> list[float] | None:
    """Embed text via API. Returns None on failure."""
    if not text or not text.strip():
        return None
    url = _embed_url()
    if not url:
        return None
    try:
        with httpx.Client(timeout=_timeout()) as client:
            r = client.post(
                url,
                json={"input": [text[:8000]], "return_dense": True},
            )
            r.raise_for_status()
            data = r.json()
            return data["data"][0].get("dense_embedding")
    except Exception as e:
        logger.warning("Embedding API unavailable: %s", e)
        return None


def _chunk_text(text: str) -> list[str]:
    """Split text into chunks by sections or paragraphs."""
    chunks = []
    current = []
    current_len = 0
    for para in re.split(r"\n\n+", text):
        para = para.strip()
        if not para:
            continue
        if current_len + len(para) > CHUNK_MAX and current:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(para)
        current_len += len(para)
        if current_len >= CHUNK_MIN:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
    if current:
        chunks.append("\n".join(current))
    return [c for c in chunks if len(c) >= 50]


def ensure_indexed() -> bool:
    """Re-index stream.md if changed. Returns True if index exists or was built."""
    if not MEMORY_FILE.exists():
        return False
    mtime = str(MEMORY_FILE.stat().st_mtime)
    if INDEX_MTIME_FILE.exists() and INDEX_MTIME_FILE.read_text().strip() == mtime:
        return VECTORS_FILE.exists()
    text = MEMORY_FILE.read_text(encoding="utf-8")
    chunks = _chunk_text(text)
    if not chunks:
        return False
    vectors = []
    for i, chunk in enumerate(chunks):
        emb = embed(chunk)
        if emb is None:
            logger.warning("Skipping chunk %d: embed failed", i)
            continue
        vectors.append({"text": chunk, "embedding": emb})
    if not vectors:
        return False
    VECTORS_FILE.parent.mkdir(exist_ok=True)
    with open(VECTORS_FILE, "w", encoding="utf-8") as f:
        for v in vectors:
            f.write(json.dumps(v, ensure_ascii=False) + "\n")
    INDEX_MTIME_FILE.write_text(mtime)
    return True


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Cosine similarity."""
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def retrieve(query: str, k: int = TOP_K) -> list[str]:
    """Retrieve top-k relevant chunks for query. Returns [] on failure."""
    if not query or not query.strip():
        return []
    if not ensure_indexed():
        return []
    q_emb = embed(query)
    if q_emb is None:
        return []
    vectors = []
    try:
        with open(VECTORS_FILE, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    vectors.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        return []
    if not vectors:
        return []
    scored = [(v["text"], _cosine_sim(v["embedding"], q_emb)) for v in vectors]
    scored.sort(key=lambda x: -x[1])
    return [t for t, _ in scored[:k]]
