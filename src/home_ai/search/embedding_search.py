from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import numpy as np
from sentence_transformers import SentenceTransformer

DEFAULT_DOC_EXTS = {".md", ".txt", ".rst"}
DEFAULT_MAX_RESULTS = 5
DEFAULT_DOCS_DIR = "docs"
DEFAULT_CHUNK_CHARS = 700
DEFAULT_CHUNK_OVERLAP = 120
DEFAULT_EMBED_MODEL = "all-MiniLM-L6-v2"
DEFAULT_INDEX_DIR = "data"
DEFAULT_INDEX_NAME = "home_ai_embeddings.npy"
DEFAULT_META_NAME = "home_ai_embeddings_meta.json"

_EMBED_CACHE = None
_META_CACHE = None
_MODEL_CACHE = None
_CACHE_LOCK = Lock()


@dataclass(frozen=True)
class SearchResult:
    title: str
    path: str
    snippet: str
    score: float


def _get_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _get_doc_roots() -> list[Path]:
    repo_root = _get_repo_root()
    default_root = repo_root / DEFAULT_DOCS_DIR
    return [default_root] if default_root.exists() else []


def _iter_text_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if root.is_dir():
            for path in root.rglob("*"):
                if path.is_file() and path.suffix.lower() in DEFAULT_DOC_EXTS:
                    files.append(path)
    return files


def _chunk_text(text: str, *, max_chars: int, overlap: int) -> list[str]:
    paragraphs = [line.strip() for line in text.splitlines()]
    blocks: list[str] = []
    current: list[str] = []
    size = 0
    for para in paragraphs:
        if not para:
            if current:
                blocks.append(" ".join(current).strip())
                current = []
                size = 0
            continue
        if size + len(para) + 1 > max_chars and current:
            blocks.append(" ".join(current).strip())
            if overlap > 0:
                tail = blocks[-1][-overlap:]
                current = [tail]
                size = len(tail)
            else:
                current = []
                size = 0
        current.append(para)
        size += len(para) + 1
    if current:
        blocks.append(" ".join(current).strip())
    return [block for block in blocks if block]


def _get_index_paths() -> tuple[Path, Path]:
    repo_root = _get_repo_root()
    index_dir = repo_root / DEFAULT_INDEX_DIR
    index_path = index_dir / DEFAULT_INDEX_NAME
    meta_path = index_dir / DEFAULT_META_NAME
    return index_path, meta_path


def _get_model() -> SentenceTransformer:
    global _MODEL_CACHE
    if _MODEL_CACHE is None:
        _MODEL_CACHE = SentenceTransformer(DEFAULT_EMBED_MODEL)
    return _MODEL_CACHE


def _normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def build_index() -> None:
    index_path, meta_path = _get_index_paths()
    index_path.parent.mkdir(parents=True, exist_ok=True)
    roots = _get_doc_roots()
    if not roots:
        raise RuntimeError("No docs directory found to build the index.")

    chunks: list[str] = []
    meta: list[dict[str, str]] = []
    for path in _iter_text_files(roots):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        doc_chunks = _chunk_text(
            text,
            max_chars=DEFAULT_CHUNK_CHARS,
            overlap=DEFAULT_CHUNK_OVERLAP,
        )
        for chunk in doc_chunks:
            if not chunk:
                continue
            chunks.append(chunk)
            meta.append({"title": path.name, "path": str(path), "text": chunk})

    if not chunks:
        raise RuntimeError("No documents to index.")

    model = _get_model()
    embeddings = model.encode(chunks, batch_size=32, show_progress_bar=False)
    embeddings = np.asarray(embeddings, dtype=np.float32)
    embeddings = _normalize_vectors(embeddings)
    np.save(str(index_path), embeddings)
    meta_path.write_text(json.dumps(meta, ensure_ascii=True, indent=2))
    clear_index_cache()
    return None

def _load_index() -> tuple[np.ndarray, list[dict[str, str]]]:
    index_path, meta_path = _get_index_paths()
    if not index_path.exists() or not meta_path.exists():
        build_index()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if not meta:
        raise RuntimeError("Index metadata is empty.")
    embeddings = np.load(str(index_path))
    if embeddings.ndim != 2:
        raise RuntimeError("Embeddings file is invalid.")
    return embeddings, meta


def _get_index_cache() -> tuple[np.ndarray, list[dict[str, str]]]:
    global _EMBED_CACHE, _META_CACHE
    if _EMBED_CACHE is None or _META_CACHE is None:
        with _CACHE_LOCK:
            if _EMBED_CACHE is None or _META_CACHE is None:
                embeddings, meta = _load_index()
                _EMBED_CACHE = embeddings
                _META_CACHE = meta
    return _EMBED_CACHE, _META_CACHE


def clear_index_cache() -> None:
    global _EMBED_CACHE, _META_CACHE
    _EMBED_CACHE = None
    _META_CACHE = None


def search_local_docs(query: str, *, max_results: int = DEFAULT_MAX_RESULTS) -> list[SearchResult]:
    query = query.strip()
    if not query:
        return []

    embeddings, meta = _get_index_cache()
    model = _get_model()
    embedding = model.encode([query], show_progress_bar=False)
    embedding = np.asarray(embedding, dtype=np.float32)
    embedding = _normalize_vectors(embedding)

    if not meta:
        return []
    if embeddings.shape[0] != len(meta):
        raise RuntimeError("Embeddings and metadata are out of sync.")
    scores = embeddings @ embedding[0]
    k = min(max_results, len(meta))
    top_indices = np.argpartition(-scores, k - 1)[:k]
    top_indices = top_indices[np.argsort(-scores[top_indices])]
    results: list[SearchResult] = []
    for idx in top_indices:
        entry = meta[int(idx)]
        results.append(
            SearchResult(
                title=entry.get("title", ""),
                path=entry.get("path", ""),
                snippet=entry.get("text", "")[:300],
                score=float(scores[int(idx)]),
            )
        )
    return results
