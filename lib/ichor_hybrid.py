"""Ichor Hybrid Scorer + Memory Trait Contract.

Fuses 4 backends into a unified retrieval interface:

  | Backend  | Source                    | Weight | Signal      |
  |----------|---------------------------|--------|-------------|
  | FTS5     | ~/.hermes/ichor.db        | 0.20   | Keyword     |
  | ChromaDB | ~/.hermes/pantheon/chroma | 0.35   | Semantic    |
  | Graph    | ~/.hermes/pantheon/graph.db| 0.25   | Relationship|
  | Events   | ~/.hermes/ichor.db        | 0.20   | Structured  |

Memory Trait Contract provides four unified tools:
  - ichor_store(namespace, key, content, category) → stores content
  - ichor_retrieve(query, limit, backends) → fused search across backends
  - ichor_forget(namespace, key) → deletes from all backends
  - ichor_health() → checks all backends

Usage:
    from lib.ichor_hybrid import HybridScorer, MemoryTrait
    scorer = HybridScorer()
    results = scorer.retrieve("SSL cert expiry", limit=10)
    health = MemoryTrait().health_check()
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ichor_hybrid")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HOME = Path.home()
_PANTHEON_LIB = _HOME / "pantheon" / "lib"
_ICHOR_DB = _HOME / ".hermes" / "ichor.db"
_CHROMA_DIR = _HOME / ".hermes" / "pantheon" / "chroma"
_GRAPH_DB = _HOME / ".hermes" / "pantheon" / "graph.db"

# Weights for fused scoring
WEIGHTS = {
    "fts5": 0.20,
    "chroma": 0.35,
    "graph": 0.25,
    "events": 0.20,
}

BACKEND_NAMES = {
    "fts5": "🔍 FTS5 (Keyword)",
    "chroma": "🧠 ChromaDB (Semantic)",
    "graph": "🔗 Graph (Relationships)",
    "events": "📋 Events (Structured)",
}


def _ensure_imports() -> None:
    """Ensure ~/pantheon/ is on sys.path."""
    pantheon_root = str(_HOME / "pantheon")
    if pantheon_root not in sys.path:
        sys.path.insert(0, pantheon_root)


# ===================================================================
# Backend Connectors
# ===================================================================


class FTS5Backend:
    """Keyword search over ichor_events via SQLite FTS5."""

    def __init__(self) -> None:
        self._db = None

    def _connect(self):
        if self._db is None:
            _ensure_imports()
            from lib.ichor_db import IchorDB  # type: ignore[import-untyped]
            self._db = IchorDB(db_path=str(_ICHOR_DB))
            self._db.connect()
        return self._db

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """FTS5 full-text search across ichor_events."""
        try:
            db = self._connect()
            events = db.query_fts(query, limit=limit)
            max_score = max((e.get("confidence", 0) for e in events), default=1.0)
            results = []
            for ev in events:
                results.append({
                    "id": f"fts5:{ev['id']}",
                    "score": round(ev.get("confidence", 0.5) / max_score, 3),
                    "backend": "fts5",
                    "type": ev.get("event_type", ""),
                    "title": ev.get("subject", ""),
                    "snippet": (ev.get("raw_text") or "")[:300],
                    "source": ev.get("session_id", ""),
                    "created_at": ev.get("created_at", ""),
                })
            return results
        except Exception as exc:
            logger.debug("FTS5 search failed: %s", exc)
            return []

    def health(self) -> bool:
        try:
            db = self._connect()
            db._conn.execute("SELECT 1 FROM ichor_events LIMIT 1")
            return True
        except Exception:
            return False


class ChromaBackend:
    """Semantic search over Athenaeum via ChromaDB."""

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(_CHROMA_DIR))
            collections = client.list_collections()
            if not collections:
                return []

            # Embed query
            embedder = _Embedder()
            if not embedder.is_available():
                return []

            query_emb = embedder.embed(query[:512])
            if not query_emb:
                return []

            results: List[Dict[str, Any]] = []
            for col in collections:
                try:
                    qr = col.query(
                        query_embeddings=[query_emb],
                        n_results=min(limit, 5),
                    )
                    ids = qr.get("ids", [[]])[0]
                    distances = qr.get("distances", [[]])[0]
                    documents = qr.get("documents", [[]])[0]
                    metadatas = qr.get("metadatas", [[]])[0]

                    for i, doc_id in enumerate(ids):
                        dist = distances[i] if i < len(distances) else 1.0
                        sim = max(0.0, 1.0 - dist)
                        doc = documents[i] if i < len(documents) else ""
                        meta = metadatas[i] if i < len(metadatas) else {}

                        results.append({
                            "id": f"chroma:{doc_id}",
                            "score": round(sim, 3),
                            "backend": "chroma",
                            "type": "document",
                            "title": meta.get("source", doc_id)[:100],
                            "snippet": doc[:300],
                            "source": col.name,
                            "created_at": meta.get("timestamp", ""),
                        })
                except Exception:
                    continue

            # Sort by score, cap
            results.sort(key=lambda x: x["score"], reverse=True)
            norm = max((r["score"] for r in results), default=1.0)
            for r in results:
                r["score"] = round(r["score"] / norm, 3) if norm > 0 else 0
            return results[:limit]

        except Exception as exc:
            logger.debug("ChromaDB search failed: %s", exc)
            return []

    def health(self) -> bool:
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(_CHROMA_DIR))
            client.heartbeat()
            return True
        except Exception:
            return False


class GraphBackend:
    """Entity relationship search via graph.db."""

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            import sqlite3
            conn = sqlite3.connect(str(_GRAPH_DB))
            conn.row_factory = sqlite3.Row

            # Search nodes by label matching
            cursor = conn.execute(
                """
                SELECT n.*, COUNT(e.id) AS edge_count
                FROM nodes n
                LEFT JOIN edges e ON e.source_id = n.id OR e.target_id = n.id
                WHERE n.label LIKE ? OR n.id LIKE ?
                GROUP BY n.id
                ORDER BY edge_count DESC
                LIMIT ?
                """,
                (f"%{query}%", f"%{query}%", limit),
            )
            rows = [dict(r) for r in cursor.fetchall()]

            if not rows:
                # No matching nodes — return empty, don't fall back to general
                conn.close()
                return []

            max_edges = max((r.get("edge_count", 1) for r in rows), default=1)
            results = []
            for r in rows:
                score = min(r.get("edge_count", 1) / max_edges, 1.0)
                results.append({
                    "id": f"graph:{r['id']}",
                    "score": round(score, 3),
                    "backend": "graph",
                    "type": r.get("type", "entity"),
                    "title": r.get("label", r["id"]),
                    "snippet": f"Type: {r.get('type', '?')} | Edges: {r.get('edge_count', 0)} | Codex: {r.get('codex', '')}",
                    "source": r.get("codex", ""),
                    "created_at": r.get("created_at", ""),
                })
            conn.close()
            return results[:limit]

        except Exception as exc:
            logger.debug("Graph search failed: %s", exc)
            return []

    def health(self) -> bool:
        try:
            import sqlite3
            conn = sqlite3.connect(str(_GRAPH_DB))
            conn.execute("SELECT 1 FROM nodes LIMIT 1")
            conn.close()
            return True
        except Exception:
            return False


class EventsBackend:
    """Structured event search over ichor_events (by type/confidence)."""

    def __init__(self) -> None:
        self._db = None

    def _connect(self):
        if self._db is None:
            _ensure_imports()
            from lib.ichor_db import IchorDB
            self._db = IchorDB(db_path=str(_ICHOR_DB))
            self._db.connect()
        return self._db

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search by matching query against subject or raw_text, ranked by confidence."""
        try:
            db = self._connect()
            conn = db._conn

            # Get recent high-confidence events that match the query terms
            cursor = conn.execute(
                """
                SELECT * FROM ichor_events
                WHERE (subject LIKE ? OR raw_text LIKE ?)
                ORDER BY confidence DESC, created_at DESC
                LIMIT ?
                """,
                (f"%{query}%", f"%{query}%", limit),
            )
            rows = [dict(r) for r in cursor.fetchall()]

            max_conf = max((r.get("confidence", 0.5) for r in rows), default=1.0)
            results = []
            for r in rows:
                results.append({
                    "id": f"events:{r['id']}",
                    "score": round(r.get("confidence", 0.5) / max_conf, 3),
                    "backend": "events",
                    "type": r.get("event_type", ""),
                    "title": r.get("subject", ""),
                    "snippet": (r.get("raw_text") or "")[:300],
                    "source": r.get("session_id", ""),
                    "created_at": r.get("created_at", ""),
                })
            return results
        except Exception as exc:
            logger.debug("Events search failed: %s", exc)
            return []

    def health(self) -> bool:
        try:
            db = self._connect()
            db._conn.execute("SELECT 1 FROM ichor_events LIMIT 1")
            return True
        except Exception:
            return False


# ===================================================================
# Embedder (inline, avoids circular deps)
# ===================================================================


class _Embedder:
    """Thin embedding wrapper — OpenRouter first, Ollama fallback."""

    def __init__(self):
        import os
        self._api_key = os.environ.get("ATHENAEUM_EMBED_API_KEY", "") or os.environ.get("OPENROUTER_API_KEY", "")
        self._model = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
        self._timeout = 30.0

    @property
    def use_openrouter(self) -> bool:
        return bool(self._api_key)

    def embed(self, text: str) -> Optional[List[float]]:
        import httpx
        try:
            if self.use_openrouter:
                resp = httpx.post(
                    "https://openrouter.ai/api/v1/embeddings",
                    headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                    json={"model": self._model, "input": text},
                    timeout=self._timeout,
                )
                resp.raise_for_status()
                return resp.json()["data"][0]["embedding"]
            else:
                resp = httpx.post(
                    "http://localhost:11434/api/embeddings",
                    json={"model": "nomic-embed-text", "prompt": text},
                    timeout=self._timeout,
                )
                resp.raise_for_status()
                return resp.json()["embedding"]
        except Exception:
            return None

    def is_available(self) -> bool:
        if self.use_openrouter:
            return True
        try:
            import httpx
            resp = httpx.get("http://localhost:11434/api/tags", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False


# ===================================================================
# Fusion Engine
# ===================================================================


def _normalize_scores(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize scores within each backend group to 0-1."""
    if not results:
        return results

    # Group by backend, find max per group
    max_per_backend: Dict[str, float] = {}
    for r in results:
        b = r.get("backend", "unknown")
        max_per_backend[b] = max(max_per_backend.get(b, 0), r.get("score", 0))

    # Normalize within each group
    for r in results:
        b_max = max_per_backend.get(r.get("backend", "unknown"), 1.0)
        if b_max > 0:
            r["score"] = round(r["score"] / b_max, 3)

    return results


def _compute_fused_score(result: Dict[str, Any]) -> float:
    """Compute fused score from backend-specific score + weight."""
    backend = result.get("backend", "unknown")
    weight = WEIGHTS.get(backend, 0.0)
    score = result.get("score", 0.0)
    return round(score * weight, 3)


# ===================================================================
# HybridScorer
# ===================================================================


class HybridScorer:
    """Fused search across all 4 backends. Gracefully degrades if a backend is down."""

    def __init__(self) -> None:
        self._fts5 = FTS5Backend()
        self._chroma = ChromaBackend()
        self._graph = GraphBackend()
        self._events = EventsBackend()
        self._backends = {
            "fts5": self._fts5,
            "chroma": self._chroma,
            "graph": self._graph,
            "events": self._events,
        }

    def retrieve(
        self,
        query: str,
        limit: int = 10,
        backends: Optional[List[str]] = None,
        min_score: float = 0.0,
    ) -> Dict[str, Any]:
        """Fused search across selected backends.

        Args:
            query: Search query.
            limit: Max results to return.
            backends: Which backends to query (default: all 4).
            min_score: Minimum fused score threshold.

        Returns:
            Dict with 'results' (sorted list), 'backends_used', 'total'.
        """
        if backends is None:
            backends = ["fts5", "chroma", "graph", "events"]

        all_results: List[Dict[str, Any]] = []
        backends_used: List[str] = []
        backend_errors: Dict[str, str] = {}

        for name in backends:
            be = self._backends.get(name)
            if be is None:
                continue
            try:
                batch = be.search(query, limit=limit)
                if batch:
                    backends_used.append(name)
                    all_results.extend(batch)
            except Exception as exc:
                backend_errors[name] = str(exc)
                logger.debug("Backend '%s' failed: %s", name, exc)

        if not all_results:
            return {
                "results": [],
                "query": query,
                "backends_used": backends_used,
                "backend_errors": backend_errors,
                "total": 0,
            }

        # Normalize scores within each backend
        all_results = _normalize_scores(all_results)

        # Compute fused scores
        for r in all_results:
            r["fused_score"] = _compute_fused_score(r)

        # Deduplicate by title + snippet similarity
        seen_titles: set = set()
        deduped: List[Dict[str, Any]] = []
        for r in sorted(all_results, key=lambda x: x["fused_score"], reverse=True):
            key = (r.get("title", "").lower()[:50], r.get("snippet", "").lower()[:80])
            if key not in seen_titles:
                seen_titles.add(key)
                deduped.append(r)

        # Sort by fused score, cap
        deduped = sorted(deduped, key=lambda x: x["fused_score"], reverse=True)

        if min_score > 0:
            deduped = [r for r in deduped if r["fused_score"] >= min_score]

        top = deduped[:limit]

        return {
            "results": top,
            "query": query,
            "backends_used": backends_used,
            "backend_errors": backend_errors,
            "total": len(top),
            "weights": WEIGHTS,
        }

    def health_check(self) -> Dict[str, Any]:
        """Check health of all backends."""
        health: Dict[str, Any] = {}
        all_healthy = True
        for name, be in self._backends.items():
            try:
                ok = be.health()
                health[name] = {
                    "healthy": ok,
                    "label": BACKEND_NAMES.get(name, name),
                    "weight": WEIGHTS.get(name, 0),
                }
                if not ok:
                    all_healthy = False
            except Exception as exc:
                health[name] = {"healthy": False, "error": str(exc)}
                all_healthy = False

        return {
            "healthy": all_healthy,
            "backends": health,
            "total_backends": len(self._backends),
            "healthy_count": sum(1 for v in health.values() if v.get("healthy")),
        }


# ===================================================================
# Memory Trait Contract
# ===================================================================


class MemoryTrait:
    """Unified memory interface — routes operations to the correct backend.

    Implements the OpenHuman-inspired contract:
        store(namespace, key, content, category, session_id)
        retrieve(query, limit, opts)
        forget(key)
        health_check()
    """

    def __init__(self) -> None:
        self._scorer = HybridScorer()

    def store(
        self,
        namespace: str = "default",
        key: str = "",
        content: str = "",
        category: str = "fact",
        session_id: str = "",
        god_name: str = "",
    ) -> Dict[str, Any]:
        """Store content, routing to the correct backend by category.

        Categories:
            - 'fact', 'preference', 'decision', 'commitment' → ichor_events (FTS5)
            - 'document', 'note', 'reference' → ChromaDB (via Athenaeum write)
            - 'entity', 'relationship' → Graph DB

        Args:
            namespace: Logical grouping (e.g. 'hermes', 'hephaestus').
            key: Unique identifier for the stored item.
            content: The content to store.
            category: Content category (determines backend routing).
            session_id: Source session ID.
            god_name: Name of the god storing.

        Returns:
            Dict with 'stored', 'backend', 'id'.
        """
        _ensure_imports()

        # Route by category
        if category in ("fact", "preference", "decision", "commitment", "insight", "blocker", "follow_up", "correction", "reference"):
            # → ichor_events (FTS5)
            from lib.ichor_db import IchorDB  # type: ignore[import-untyped]
            db = IchorDB(db_path=str(_ICHOR_DB))
            db.connect()
            event_id = db.insert_event(
                session_id=session_id or key,
                event_type=category,
                subject=key or content[:60],
                predicate=category,
                object=content,
                confidence=0.9,
                source="manual",
                raw_text=content,
                god_name=god_name or namespace,
            )
            db.close()
            return {"stored": True, "backend": "fts5", "id": f"fts5:{event_id}", "namespace": namespace}

        elif category in ("entity", "relationship"):
            # → Graph DB
            import sqlite3
            conn = sqlite3.connect(str(_GRAPH_DB))
            now = datetime.now(timezone.utc).isoformat()
            node_id = key or f"manual:{namespace}:{hash(content) % 10**8}"
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO nodes (id, type, codex, label, metadata, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (node_id, category, namespace, key or content[:60], json.dumps({"source": "ichor_store"}), now, now),
                )
                conn.commit()
            except Exception as exc:
                logger.debug("Graph store failed: %s", exc)
            conn.close()
            return {"stored": True, "backend": "graph", "id": f"graph:{node_id}", "namespace": namespace}

        else:
            # → ChromaDB (via Athenaeum write) — store as a note
            athenaeum_path = _ensure_imports()
            notes_dir = _HOME / "athenaeum" / "Codex-Pantheon" / "ichor-notes"
            notes_dir.mkdir(parents=True, exist_ok=True)
            note_path = notes_dir / f"{namespace}--{key.replace('/', '--')}.md"
            note_path.write_text(
                f"---\nnamespace: {namespace}\nkey: {key}\ncategory: {category}\n"
                f"stored_at: {datetime.now(timezone.utc).isoformat()}\n"
                f"session_id: {session_id}\n---\n\n{content}\n",
                encoding="utf-8",
            )
            return {"stored": True, "backend": "athenaeum", "id": str(note_path.relative_to(_HOME)), "namespace": namespace}

    def retrieve(
        self,
        query: str,
        limit: int = 10,
        backends: Optional[List[str]] = None,
        min_score: float = 0.0,
        output_format: str = "json",
    ) -> Any:
        """Unified retrieval across all backends (delegates to HybridScorer).

        Args:
            query: Search query.
            limit: Max results.
            backends: Which backends to search (default: all).
            min_score: Minimum fused score.
            output_format: 'json' or 'markdown'.

        Returns:
            JSON dict or formatted markdown string.
        """
        result = self._scorer.retrieve(
            query=query,
            limit=limit,
            backends=backends,
            min_score=min_score,
        )

        if output_format == "json":
            return result

        # Markdown
        if not result["results"]:
            return f"🔍 No results for `{query}` across any backend."

        lines = [f"## 🔍 Hybrid Search: `{query}`", ""]

        for r in result["results"]:
            backend_name = BACKEND_NAMES.get(r.get("backend", ""), r.get("backend", ""))
            fused = r.get("fused_score", r.get("score", 0))
            icon_map = {"blocker": "🚧", "commitment": "📋", "decision": "🎯",
                        "follow_up": "🔁", "insight": "💡", "document": "📄",
                        "entity": "🔗", "correction": "🔧", "fact": "📌"}
            icon = icon_map.get(r.get("type", ""), "•")
            lines.append(f"**{r.get('title', '?')}** {icon}")
            lines.append(f"  `{backend_name}` · fused: {fused:.2f} · type: {r.get('type', '?')}")
            if r.get("snippet"):
                lines.append(f"  > {r['snippet']}")
            lines.append("")

        lines.append(f"---")
        lines.append(f"_Backends: {', '.join(result['backends_used'])} · {result['total']} results_")
        return "\n".join(lines)

    def forget(self, key: str) -> Dict[str, Any]:
        """Delete from all backends by key prefix (e.g. 'fts5:42', 'graph:node:...')."""
        deleted = []
        prefix, _, rest = key.partition(":")

        if prefix == "fts5" and rest:
            try:
                _ensure_imports()
                from lib.ichor_db import IchorDB
                db = IchorDB(db_path=str(_ICHOR_DB))
                db.connect()
                db._conn.execute("DELETE FROM ichor_events WHERE id = ?", (int(rest),))
                db._conn.commit()
                db.close()
                deleted.append("fts5")
            except Exception as exc:
                logger.debug("forget fts5 failed: %s", exc)

        elif prefix == "graph" and rest:
            try:
                import sqlite3
                conn = sqlite3.connect(str(_GRAPH_DB))
                conn.execute("DELETE FROM edges WHERE source_id = ? OR target_id = ?", (rest, rest))
                conn.execute("DELETE FROM nodes WHERE id = ?", (rest,))
                conn.commit()
                conn.close()
                deleted.append("graph")
            except Exception as exc:
                logger.debug("forget graph failed: %s", exc)

        elif prefix == "chroma" and rest:
            logger.debug("ChromaDB forget not yet implemented for single documents")

        return {"forgotten": True, "key": key, "deleted_from": deleted}

    def health_check(self) -> Dict[str, Any]:
        """Health check for all backends."""
        return self._scorer.health_check()


# ===================================================================
# Quick summary formatter (for CLI/AI consumption)
# ===================================================================


def format_health_summary(health: Dict[str, Any]) -> str:
    """Format health check as a scannable string."""
    lines = [f"## 🏥 Ichor Memory Health"]
    lines.append(f"_{health['healthy_count']}/{health['total_backends']} backends healthy_\n")

    for name, info in health.get("backends", {}).items():
        status = "✅" if info.get("healthy") else "❌"
        label = info.get("label", name)
        weight = info.get("weight", 0)
        err = f" — {info.get('error', '')}" if info.get("error") else ""
        lines.append(f"{status} **{label}** (weight: {weight:.0%}){err}")

    return "\n".join(lines)


# ===================================================================
# CLI entry point
# ===================================================================


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Ichor Hybrid Scorer + Memory Trait Contract"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Retrieve
    p_ret = sub.add_parser("retrieve", help="Fused search across backends")
    p_ret.add_argument("query", help="Search query")
    p_ret.add_argument("--limit", "-l", type=int, default=10)
    p_ret.add_argument("--backends", "-b", nargs="+",
                       choices=["fts5", "chroma", "graph", "events"],
                       default=["fts5", "chroma", "graph", "events"])
    p_ret.add_argument("--min-score", "-m", type=float, default=0.0)
    p_ret.add_argument("--markdown", "-d", action="store_true", help="Output markdown instead of JSON")

    # Store
    p_st = sub.add_parser("store", help="Store content")
    p_st.add_argument("--key", "-k", required=True)
    p_st.add_argument("--content", "-c", required=True)
    p_st.add_argument("--namespace", "-n", default="default")
    p_st.add_argument("--category", "-t", default="fact",
                      choices=["fact", "preference", "decision", "commitment",
                               "insight", "blocker", "follow_up", "document", "entity"])
    p_st.add_argument("--session-id", "-s", default="")
    p_st.add_argument("--god-name", "-g", default="")

    # Health
    sub.add_parser("health", help="Check backend health")

    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)

    trait = MemoryTrait()

    if args.command == "retrieve":
        result = trait.retrieve(
            query=args.query,
            limit=args.limit,
            backends=args.backends,
            min_score=args.min_score,
            output_format="markdown" if args.markdown else "json",
        )
        if args.markdown:
            print(result)
        else:
            print(json.dumps(result, indent=2, default=str))

    elif args.command == "store":
        result = trait.store(
            namespace=args.namespace,
            key=args.key,
            content=args.content,
            category=args.category,
            session_id=args.session_id,
            god_name=args.god_name,
        )
        print(json.dumps(result, indent=2))

    elif args.command == "health":
        health = trait.health_check()
        print(json.dumps(health, indent=2))
        print()
        print(format_health_summary(health))


if __name__ == "__main__":
    main()
