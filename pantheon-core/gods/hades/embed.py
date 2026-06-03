"""Hades embed phase.

Phase 2 of the pipeline. Two responsibilities:
  1. `_Embedder` — wraps OpenRouter (primary) / Ollama (fallback) for
     embedding text. Configurable via env vars.
  2. `embed_missing_files` — walks the filesystem, identifies files
     missing from ChromaDB, embeds them.

Brittleness fix #7 (2026-06-03): the prior version swallowed
`Exception` in the per-file embed path. Replaced with `logger.exception`
so failures (e.g. the OpenRouter 768/1024 dim mismatch that was
silently failing 531 files) show up in the log.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List

import httpx

from .paths import (
    ARCHIVE_DIR_NAME,
    ATHENAEUM_ROOT,
    CHROMA_DIR,
    DISTILLED_DIR_NAME,
    EMBEDDABLE_EXTS,
    SESSIONS_DIR_NAME,
)
from .models import HadesReport

logger = logging.getLogger(__name__)


class _Embedder:
    """Thin embedding wrapper — OpenRouter first, Ollama fallback.

    Configurable via env vars:
      ATHENAEUM_EMBED_API_KEY  (or OPENROUTER_API_KEY)
      ATHENAEUM_EMBED_PROVIDER (set to "ollama" to force local)
      ATHENAEUM_EMBED_MODEL    (default: nomic-embed-text:v1.5)
    """

    def __init__(self) -> None:
        self._api_key = os.environ.get("ATHENAEUM_EMBED_API_KEY", "") or os.environ.get("OPENROUTER_API_KEY", "")
        self._model = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
        self._timeout = 30.0
        self._ollama_model = os.environ.get("ATHENAEUM_EMBED_MODEL", "nomic-embed-text:v1.5")

    @property
    def use_openrouter(self) -> bool:
        provider = os.environ.get("ATHENAEUM_EMBED_PROVIDER", "").lower()
        if provider == "ollama":
            return False
        return bool(self._api_key)

    def embed(self, text: str) -> List[float]:
        """Embed text and return a single averaged vector."""

        def _call_api(payload: dict) -> List[float]:
            if self.use_openrouter:
                url = "https://openrouter.ai/api/v1/embeddings"
                headers = {
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                }
            else:
                url = "http://localhost:11434/api/embeddings"
                headers = {"Content-Type": "application/json"}
                payload.setdefault("options", {})["num_ctx"] = 2048
            resp = httpx.post(url, headers=headers, json=payload, timeout=self._timeout)
            resp.raise_for_status()
            if self.use_openrouter:
                return resp.json()["data"][0]["embedding"]
            return resp.json()["embedding"]

        CHUNK_SIZE = 1500
        CHUNK_OVERLAP = 100
        MAX_CHUNKS = 20

        if len(text) <= CHUNK_SIZE:
            if self.use_openrouter:
                return _call_api({"model": self._model, "input": text})
            return _call_api({"model": self._ollama_model, "prompt": "search_document: " + text})

        # Chunk and average
        chunks: List[str] = []
        start = 0
        while start < len(text) and len(chunks) < MAX_CHUNKS:
            end = min(start + CHUNK_SIZE, len(text))
            if end < len(text):
                cut = text.rfind(". ", start + CHUNK_SIZE - 200, end)
                if cut > start + CHUNK_SIZE // 2:
                    end = cut + 1
            chunks.append(text[start:end])
            start = end - CHUNK_OVERLAP if end < len(text) else end

        vectors: List[List[float]] = []
        for chunk in chunks:
            if self.use_openrouter:
                v = _call_api({"model": self._model, "input": chunk})
            else:
                v = _call_api({"model": self._ollama_model, "prompt": "search_document: " + chunk})
            vectors.append(v)

        if not vectors:
            raise RuntimeError("embedding failed for all chunks")

        dim = len(vectors[0])
        avg = [0.0] * dim
        for v in vectors:
            for i in range(dim):
                avg[i] += v[i]
        return [x / len(vectors) for x in avg]

    def is_available(self) -> bool:
        """Check if the embedder is reachable."""
        if self.use_openrouter:
            return True
        try:
            resp = httpx.get("http://localhost:11434/api/tags", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False


def _get_chroma_client():
    """Get or create a ChromaDB PersistentClient."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        client.heartbeat()
        return client
    except Exception as exc:
        logger.warning("ChromaDB unavailable: %s", exc)
        return None


def _partition_for(codex: str) -> str:
    slug = codex.lower().replace("-", "_").replace(" ", "_")
    return f"pantheon_{slug}"


def _embed_file(file_path: str, content: str, codex_hint: str = "") -> bool:
    """Embed a single file into ChromaDB. Returns True on success."""
    try:
        client = _get_chroma_client()
        if client is None:
            return False

        embedder = _Embedder()
        if not embedder.is_available():
            logger.warning("  → Embedder not available — skipping %s", Path(file_path).name)
            return False

        rel = Path(file_path).relative_to(ATHENAEUM_ROOT)
        codex = codex_hint or rel.parts[0]
        col_name = _partition_for(codex)

        try:
            collection = client.get_collection(col_name)
        except Exception:
            collection = client.create_collection(col_name)

        embedding = embedder.embed(content[:4000])
        collection.upsert(
            ids=[str(Path(file_path).resolve())],
            embeddings=[embedding],
            documents=[content],
            metadatas=[{"source": file_path, "codex": codex, "filename": Path(file_path).name}],
        )
        logger.info("  → Embedded: %s → %s", rel, col_name)
        return True
    except Exception as exc:
        # Brittleness fix #7: log the full exception instead of swallowing.
        # The prior `logger.warning(...)` with `str(exc)` was hiding the
        # stack trace and the actual error class — making the 531-files-
        # not-embedded warning undebuggable.
        logger.exception("  → Embed failed for %s", file_path)
        return False


def embed_missing_files(max_files: int = 30) -> Dict[str, Any]:
    """Backfill filesystem files not yet in ChromaDB, up to max_files per run.

    Walks each Codex, checks ChromaDB via per-collection query (not full dump),
    and embeds any missing files. Capped at max_files to avoid runaway runtime.

    Args:
        max_files: Max files to embed per run (default 200).

    Returns: {
        "embedded": int,      # files newly embedded
        "skipped": int,       # files skipped (unavailable embedder)
        "failed": int,        # files that errored
        "remaining": int,     # files still unembedded (estimate)
        "total_before": int,  # vectors in ChromaDB before backfill
        "total_after": int,   # vectors in ChromaDB after backfill
    }
    """
    result: Dict[str, Any] = {
        "embedded": 0,
        "skipped": 0,
        "failed": 0,
        "remaining": 0,
        "total_before": 0,
        "total_after": 0,
    }

    client = _get_chroma_client()
    if client is None:
        logger.error("ChromaDB unavailable — cannot embed missing files")
        return result

    embedder = _Embedder()
    if not embedder.is_available():
        logger.warning("Embedder not available — skipping embed backfill")
        result["skipped"] = -1
        return result

    # Count existing vectors
    total_before = sum(col.count() for col in client.list_collections())
    result["total_before"] = total_before

    # Walk filesystem, check each file against ChromaDB, embed if missing
    for codex_dir in sorted(ATHENAEUM_ROOT.iterdir()):
        if not codex_dir.is_dir() or not codex_dir.name.startswith("Codex-"):
            continue
        codex = codex_dir.name
        col_name = _partition_for(codex)

        # Get or create the ChromaDB collection for this codex
        try:
            collection = client.get_collection(col_name)
        except Exception:
            collection = client.create_collection(col_name)

        for f in codex_dir.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix.lower() not in EMBEDDABLE_EXTS:
                continue
            if f.name == "INDEX.md":
                continue
            rel = f.relative_to(ATHENAEUM_ROOT)
            parts = rel.parts
            if len(parts) > 1 and parts[1] in (ARCHIVE_DIR_NAME, DISTILLED_DIR_NAME, SESSIONS_DIR_NAME):
                continue

            abs_path = str(f.resolve())

            # Check if already embedded via per-file lookup
            try:
                existing = collection.get(ids=[abs_path])
                if existing and existing.get("ids"):
                    continue
            except Exception as exc:
                # Brittleness fix #7: log the actual cause of the
                # "already embedded?" check failing. Previously silent
                # pass, which is how the dim mismatch went unnoticed.
                logger.debug("  → Per-file lookup failed for %s: %s", abs_path, exc)

            # Read + embed
            try:
                content = f.read_text(encoding="utf-8")
            except Exception:
                result["failed"] += 1
                continue

            ok = _embed_file(abs_path, content, codex)
            if ok:
                result["embedded"] += 1
            else:
                result["failed"] += 1

            # Check cap
            if result["embedded"] + result["failed"] >= max_files:
                break

        if result["embedded"] + result["failed"] >= max_files:
            break

    # Compute remaining (approximate: count how many files still not in chroma)
    remaining = 0
    for codex_dir in sorted(ATHENAEUM_ROOT.iterdir()):
        if not codex_dir.is_dir() or not codex_dir.name.startswith("Codex-"):
            continue
        try:
            col = client.get_collection(_partition_for(codex_dir.name))
        except Exception:
            col = None
        for f in codex_dir.rglob("*"):
            if not f.is_file() or f.suffix.lower() not in EMBEDDABLE_EXTS:
                continue
            if f.name == "INDEX.md":
                continue
            rel = f.relative_to(ATHENAEUM_ROOT)
            parts = rel.parts
            if len(parts) > 1 and parts[1] in (ARCHIVE_DIR_NAME, DISTILLED_DIR_NAME, SESSIONS_DIR_NAME):
                continue
            abs_path = str(f.resolve())
            try:
                if col:
                    existing = col.get(ids=[abs_path])
                    if not existing or not existing.get("ids"):
                        remaining += 1
            except Exception:
                remaining += 1
    result["remaining"] = remaining

    # Re-count after backfill
    try:
        client2 = _get_chroma_client()
        if client2:
            result["total_after"] = sum(col.count() for col in client2.list_collections())
        else:
            result["total_after"] = result["total_before"]
    except Exception:
        result["total_after"] = result["total_before"]

    return result


def _recheck_embedded_counts(report: HadesReport) -> None:
    """Re-read ChromaDB counts and update the report's health data with accurate embedded numbers.

    Builds a lookup from collection name → codex name by matching KNOWN_CODEXES
    via _partition_for(), which avoids the capitalization roundtrip problem.

    Must be called AFTER embed_missing_files() so the report reflects post-embed state.
    """
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))

        # Build reverse map: partition name → codex name (e.g. pantheon_codex_skc → Codex-SKC)
        partition_to_codex: Dict[str, str] = {}
        for codex_name in list(report.health.get("codexes", {}).keys()):
            partition_to_codex[_partition_for(codex_name)] = codex_name

        from .paths import KNOWN_CODEXES as _KC
        for codex_name in list(_KC):
            if codex_name not in partition_to_codex:
                partition_to_codex[_partition_for(codex_name)] = codex_name

        # Read ChromaDB collections and map back to codex names
        chroma_counts: Dict[str, int] = {}
        for col in client.list_collections():
            codex_name = partition_to_codex.get(col.name)
            if codex_name:
                chroma_counts[codex_name] = col.count()

        # Update each codex entry with real embedded count
        for codex_name, info in report.health.get("codexes", {}).items():
            info["embedded"] = chroma_counts.get(codex_name, 0)

        # Regenerate fs_unembedded from actual state
        orphans = report.health.setdefault("orphans", {"chroma_only": [], "fs_unembedded": []})
        fs_unembedded: List[str] = []
        for codex_name, info in report.health.get("codexes", {}).items():
            embeddable = info.get("embeddable", 0)
            embedded = info.get("embedded", 0)
            if embeddable > embedded:
                codex_dir = ATHENAEUM_ROOT / codex_name
                if codex_dir.is_dir():
                    for f in codex_dir.rglob("*"):
                        if not f.is_file() or f.suffix.lower() not in EMBEDDABLE_EXTS:
                            continue
                        if f.name == "INDEX.md":
                            continue
                        rel = f.relative_to(ATHENAEUM_ROOT)
                        parts = rel.parts
                        if len(parts) > 1 and parts[1] in (ARCHIVE_DIR_NAME, DISTILLED_DIR_NAME, SESSIONS_DIR_NAME):
                            continue
                        abs_p = str(f.resolve())
                        try:
                            col = client.get_collection(_partition_for(codex_name))
                            existing = col.get(ids=[abs_p])
                            if not existing or not existing.get("ids"):
                                fs_unembedded.append(str(rel))
                        except Exception:
                            fs_unembedded.append(str(rel))
                        if len(fs_unembedded) >= 50:
                            break
        orphans["fs_unembedded"] = fs_unembedded

    except Exception as exc:
        logger.warning("Failed to recheck embedded counts: %s", exc)
