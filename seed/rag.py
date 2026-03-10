"""RAG: ChromaDB + BGE embedding + reranker."""

from __future__ import annotations

import os
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_PATH = PROJECT_ROOT / "data" / "rag" / "chroma"
CHUNK_SIZE = 2048  # ~512 tokens
CHUNK_OVERLAP = 256  # ~64 tokens
COLLECTION_NAME = "knowledge"
RECALL_COLLECTION_NAME = "recall"


def _get_env(key: str, alt: str = "") -> str:
    return os.getenv(key) or os.getenv(alt) or ""


def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Call BGE embedding API, return list of vectors."""
    base_url = _get_env("LOCAL_AI_EMBEDDING_BASE_URL") or "http://localhost:9001"
    if not texts:
        return []
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            f"{base_url.rstrip('/')}/v1/embeddings",
            json={"input": texts, "return_dense": True, "return_sparse": False},
        )
        resp.raise_for_status()
        data = resp.json()
    return [item.get("dense_embedding", []) for item in data.get("data", [])]


def _rerank(query: str, documents: list[str], top_n: int = 5) -> list[tuple[str, float]]:
    """Rerank documents by relevance. Returns [(doc, score), ...]."""
    base_url = _get_env("LOCAL_AI_RERANKER_BASE_URL") or "http://localhost:9002"
    if not documents:
        return []
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{base_url.rstrip('/')}/v1/rerank",
            json={"query": query, "documents": documents, "normalize": True, "top_n": top_n},
        )
        resp.raise_for_status()
        data = resp.json()
    results = data.get("results", [])
    return [(r.get("document", ""), r.get("relevance_score", 0)) for r in results]


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start = end - overlap
    return chunks


def _get_collection():
    """Get or create ChromaDB collection. Uses pre-computed embeddings (no default embed fn)."""
    import chromadb
    from chromadb.config import Settings

    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH), settings=Settings(anonymized_telemetry=False))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _get_recall_collection():
    """Get or create recall collection (session-history, evolution-log). Same settings as knowledge."""
    import chromadb
    from chromadb.config import Settings

    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH), settings=Settings(anonymized_telemetry=False))
    return client.get_or_create_collection(
        name=RECALL_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def recall_index(path: str) -> str:
    """Index file into recall collection. Chunks with optional timestamp metadata for salience."""
    target = (PROJECT_ROOT / path).resolve()
    if not target.exists():
        return f"[ERROR] Path not found: {path}"

    import re
    from datetime import datetime

    content = target.read_text(encoding="utf-8", errors="replace")
    chunks = _chunk_text(content)
    if not chunks:
        return "No text to index."

    # Parse timestamps from ## YYYY-MM-DD HH:MM headers for salience
    ids_to_add = []
    docs_to_add = []
    metadatas = []
    for i, chunk in enumerate(chunks):
        chunk_id = f"{path}:{i}"
        ids_to_add.append(chunk_id)
        docs_to_add.append(chunk)
        ts = None
        for line in chunk.split("\n")[:5]:
            m = re.match(r"^##\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", line)
            if m:
                try:
                    dt = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M")
                    ts = dt.isoformat()
                except ValueError:
                    pass
                break
        metadatas.append({"timestamp": ts or datetime.now().isoformat(), "source": path})

    try:
        embeddings = _embed_texts(docs_to_add)
        if len(embeddings) != len(docs_to_add):
            return f"[ERROR] Embedding count mismatch: {len(embeddings)} vs {len(docs_to_add)}"

        coll = _get_recall_collection()
        try:
            coll.delete(where={"source": path})
        except Exception:
            pass
        coll.add(ids=ids_to_add, embeddings=embeddings, documents=docs_to_add, metadatas=metadatas)
        return f"OK: indexed {len(docs_to_add)} chunks from {path} into recall"
    except Exception as e:
        return f"[ERROR] {e}"


def recall_search(query: str, top_n: int = 5, max_chars: int = 3000) -> str:
    """Search recall collection by query. Returns concatenated results, max max_chars. Applies salience filter if memory_utils available."""
    try:
        coll = _get_recall_collection()
        count = coll.count()
        if count == 0:
            return ""

        query_embedding = _embed_texts([query])
        if not query_embedding:
            return ""

        results = coll.query(
            query_embeddings=query_embedding,
            n_results=min(top_n * 2, count),
            include=["documents", "metadatas", "distances"],
        )
        docs = results.get("documents", [[]])[0]
        meta_list = results.get("metadatas")
        if meta_list and meta_list[0]:
            meta_list = meta_list[0]
        else:
            meta_list = [{}] * len(docs)

        if not docs:
            return ""

        doc_to_meta = {d: (meta_list[i] if i < len(meta_list) else {}) for i, d in enumerate(docs)}

        # Rerank for better relevance
        reranked = _rerank(query, docs, top_n=top_n)
        items = []
        for doc, score in reranked:
            meta = doc_to_meta.get(doc, {})
            items.append({
                "content": doc,
                "timestamp": meta.get("timestamp") if isinstance(meta, dict) else None,
                "importance": float(score) if score else 1.0,
            })

        # Apply salience filter (Forgetting curves)
        try:
            from memory_utils import filter_by_salience

            items = filter_by_salience(items)
        except ImportError:
            pass

        out_parts = []
        total = 0
        for item in items:
            c = item.get("content", "")
            if total + len(c) > max_chars:
                out_parts.append(c[: max_chars - total] + "...")
                break
            out_parts.append(c)
            total += len(c)
        return "\n\n---\n\n".join(out_parts) if out_parts else ""
    except Exception:
        return ""


def rag_index(path: str) -> str:
    """Index file or directory. Chunks, embeds, adds to ChromaDB."""
    target = (PROJECT_ROOT / path).resolve()
    if not target.exists():
        return f"[ERROR] Path not found: {path}"

    texts_to_index: list[tuple[str, str]] = []  # (id_prefix, chunk_text)

    if target.is_file():
        if target.suffix.lower() in (".md", ".txt", ".py", ".json", ".yaml", ".yml", ".rst"):
            content = target.read_text(encoding="utf-8", errors="replace")
            chunks = _chunk_text(content)
            for i, chunk in enumerate(chunks):
                texts_to_index.append((f"{path}:{i}", chunk))
        else:
            return f"[ERROR] Unsupported file type: {target.suffix}"
    else:
        for f in target.rglob("*"):
            if f.is_file() and f.suffix.lower() in (".md", ".txt", ".py", ".json", ".yaml", ".yml", ".rst"):
                rel = str(f.relative_to(PROJECT_ROOT))
                content = f.read_text(encoding="utf-8", errors="replace")
                chunks = _chunk_text(content)
                for i, chunk in enumerate(chunks):
                    texts_to_index.append((f"{rel}:{i}", chunk))

    if not texts_to_index:
        return "No text to index."

    try:
        ids = [t[0] for t in texts_to_index]
        docs = [t[1] for t in texts_to_index]
        embeddings = _embed_texts(docs)
        if len(embeddings) != len(docs):
            return f"[ERROR] Embedding count mismatch: {len(embeddings)} vs {len(docs)}"

        coll = _get_collection()
        coll.add(ids=ids, embeddings=embeddings, documents=docs)
        return f"OK: indexed {len(docs)} chunks from {path}"
    except httpx.HTTPStatusError as e:
        return f"[ERROR] Embedding API: {e.response.status_code}"
    except Exception as e:
        return f"[ERROR] {e}"


def rag_index_text(text: str, metadata: dict | None = None) -> str:
    """Index arbitrary text into knowledge collection. For sleep consolidation, etc."""
    if not text or not text.strip():
        return "[ERROR] Empty text"
    from datetime import datetime

    chunks = _chunk_text(text)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    meta = dict(metadata or {}, source="sleep", timestamp=datetime.now().isoformat())
    ids = [f"sleep:{ts}:{i}" for i in range(len(chunks))]
    metadatas = [meta] * len(chunks)
    try:
        embeddings = _embed_texts(chunks)
        if len(embeddings) != len(chunks):
            return f"[ERROR] Embedding count mismatch"
        coll = _get_collection()
        coll.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
        return f"OK: indexed {len(chunks)} chunks into knowledge"
    except Exception as e:
        return f"[ERROR] {e}"


def rag_index_evolution() -> str:
    """Index evolution-log, session-history, recent git log and diffs into RAG. Agent can search own experience."""
    import subprocess

    memory_dir = PROJECT_ROOT / "data" / "memory"
    evolution_path = memory_dir / "evolution-log.md"
    session_path = memory_dir / "session-history.md"
    out_path = memory_dir / "knowledge" / "evolution_index.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    chunks = ["# Evolution and experience index\n\n"]

    if evolution_path.exists():
        chunks.append("## evolution-log\n\n" + evolution_path.read_text(encoding="utf-8"))

    if session_path.exists():
        text = session_path.read_text(encoding="utf-8")
        chunks.append("\n## session-history (recent)\n\n" + text[-6000:])

    if (PROJECT_ROOT / ".git").exists():
        try:
            log = subprocess.run(
                ["git", "log", "-15", "--oneline", "--no-decorate"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
            )
            if log.stdout:
                chunks.append("\n## git log (recent)\n\n" + log.stdout)
            diff = subprocess.run(
                ["git", "log", "-3", "-p", "--no-decorate", "--no-color"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
            )
            if diff.stdout and len(diff.stdout) < 30000:
                chunks.append("\n## recent diffs\n\n" + diff.stdout)
        except Exception:
            pass

    content = "\n".join(chunks)
    if len(content) < 200:
        return "Not enough evolution data to index"
    out_path.write_text(content, encoding="utf-8")
    return rag_index(str(out_path.relative_to(PROJECT_ROOT)))


def rag_list() -> str:
    """List indexed documents (short metadata). Use rag_fetch(id) to load full content. Progressive disclosure."""
    try:
        coll = _get_collection()
        count = coll.count()
        if count == 0:
            return "RAG is empty. Use rag_index(path) first."
        data = coll.get(include=["documents"])
        ids = data["ids"]
        docs = data["documents"]
        seen: dict[str, str] = {}
        for doc_id, doc in zip(ids, docs):
            base = doc_id.rsplit(":", 1)[0] if ":" in doc_id else doc_id
            if base not in seen:
                preview = (doc[:80] + "...") if len(doc) > 80 else doc
                seen[base] = preview
        lines = [f"{i+1}. {p} — {(preview[:55] + '...') if len(preview) > 55 else preview}" for i, (p, preview) in enumerate(seen.items())]
        return f"Indexed {len(seen)} docs, {count} chunks:\n" + "\n".join(lines[:50])
    except Exception as e:
        return f"[ERROR] {e}"


def rag_fetch(doc_id: str) -> str:
    """Fetch full document by id. Use rag_list to see available ids. Supports prefix: 'path' fetches path:0, path:1, ..."""
    try:
        coll = _get_collection()
        if ":" in doc_id:
            data = coll.get(ids=[doc_id], include=["documents"])
        else:
            data = coll.get(include=["documents"])
            ids = data["ids"]
            docs = data["documents"]
            matching = [(i, d) for i, d in zip(ids, docs) if i.startswith(doc_id + ":") or i == doc_id]
            if not matching:
                return f"[ERROR] No document with id prefix: {doc_id}"
            return "\n\n---\n\n".join(d for _, d in matching)
        if not data["ids"]:
            return f"[ERROR] No document with id: {doc_id}"
        return data["documents"][0]
    except Exception as e:
        return f"[ERROR] {e}"


def rag_search(query: str, top_k: int = 5) -> str:
    """Search knowledge base. Embed query, search ChromaDB, rerank, return top docs."""
    try:
        coll = _get_collection()
        count = coll.count()
        if count == 0:
            return "RAG is empty. Use rag_index(path) to index files first."

        query_embedding = _embed_texts([query])
        if not query_embedding:
            return "[ERROR] Failed to embed query"

        results = coll.query(
            query_embeddings=query_embedding,
            n_results=min(top_k * 2, count),
        )
        docs = results.get("documents", [[]])[0]
        if not docs:
            return "No results."

        reranked = _rerank(query, docs, top_n=top_k)
        lines = []
        for i, (doc, score) in enumerate(reranked, 1):
            preview = (doc[:300] + "...") if len(doc) > 300 else doc
            lines.append(f"{i}. [{score:.3f}] {preview}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"[ERROR] {e}"
