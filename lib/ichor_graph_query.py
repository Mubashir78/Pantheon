"""Ichor Graph Query — Multi-hop NL Query Engine for the Pantheon Knowledge Graph.

Translates natural language questions into multi-hop graph traversals:

    "What tools does Hermes use?"
    → Entity: Hermes, Relation: uses, Target type: tool
    → Walk: entity:hermes --uses--> tool nodes
    → Returns: Telegram, Discord, God Bridge, Messaging

Architecture:
    NL Query → Parser → (anchor, relation, target_type, temporal)
                    ↓
              Entity Resolver → node ID(s)
                    ↓
              Relation Mapper → edge type(s)
                    ↓
              Multi-hop Walker → breadth-first traversal
                    ↓
              Path Builder → formatted results

Usage:
    from lib.ichor_graph_query import GraphQueryEngine
    engine = GraphQueryEngine()
    result = engine.query("What tools does Hermes use?", hops=2)

CLI:
    python3 ~/pantheon/lib/ichor_graph_query.py "What does Hermes use?"
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("ichor_graph_query")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_GRAPH_DB = Path.home() / ".hermes" / "pantheon" / "graph.db"

# ---------------------------------------------------------------------------
# NL → Edge Type Mapping
# ---------------------------------------------------------------------------

# Patterns that map natural language verbs → edge types
# Ordered by specificity (longer matches first)
NL_RELATION_MAP: List[Tuple[str, str, bool]] = [
    # (regex_pattern, edge_type, reverse_direction)
    # "uses" → uses (forward)
    (r"\b(?:uses?|using|utilizes?|employs?)\b", "uses", False),
    # "used by" → uses (reverse)
    (r"\b(?:used\s+by|utilized\s+by)\b", "uses", True),
    # "runs on / running on" → runs_on (forward)
    (r"\b(?:runs?\s+on|running\s+on|hosted?\s+on|deployed?\s+on)\b", "runs_on", False),
    # "run by / hosted by / deployed by" → runs_on (reverse)
    (r"\b(?:run\s+by|hosted\s+by|deployed\s+by)\b", "runs_on", True),
    # "part of / belongs to" → part_of (forward)
    (r"\b(?:part\s+of|belongs?\s+to)\b", "part_of", False),
    # "contains" → contains (forward)
    (r"\b(?:contains?|includes?|hold?s?)\b", "contains", False),
    # "contained by / included in" → contains (reverse)
    (r"\b(?:contained\s+by|included?\s+in)\b", "contains", True),
    # "requires / needs" → requires (forward)
    (r"\b(?:requires?|needs?|depends?\s+on)\b", "requires", False),
    # "required by / needed by" → requires (reverse)
    (r"\b(?:required\s+by|needed\s+by)\b", "requires", True),
    # "depends on" → depends_on
    (r"\bdepends?\s+on\b", "depends_on", False),
    # "created by / built by / made by" → created_by (reverse)
    (r"\b(?:created\s+by|built\s+by|made\s+by|authored?\s+by)\b", "created_by", True),
    # "creates / builds / makes / created" → created_by (forward)
    (r"\b(?:creates?|created|builds?|built|makes?|made)\b", "created_by", False),
    # "owns" → owned_by (forward)
    (r"\b(?:owns?|possesses?)\b", "owned_by", False),
    # "owned by" → owned_by (reverse)
    (r"\b(?:owned\s+by)\b", "owned_by", True),
    # "located in / lives in" → located_in (forward)
    (r"\b(?:located\s+in|lives?\s+in|situated\s+in)\b", "located_in", False),
    # "references" → references (forward)
    (r"\b(?:references?|mentions?|cites?|links?\s+to)\b", "references", False),
    # "supports" → supports (forward)
    (r"\b(?:supports?|provides?)\b", "supports", False),
    # "communicates with / talks to" → communicates_with
    (r"\b(?:communicates?\s+with|talks?\s+to|interfaces?\s+with)\b", "communicates_with", False),
    # "implements" → implements (forward)
    (r"\b(?:implements?|realizes?)\b", "implements", False),
    # "blocks" → blocks (forward)
    (r"\b(?:blocks?|prevents?|hinders?)\b", "blocks", False),
    # "replaces" → replaces (forward)
    (r"\b(?:replaces?|succeeds?)\b", "replaces", False),
    # "follows" → follows (forward)
    (r"\b(?:follows?|comes\s+after)\b", "follows", False),
    # "precedes" → precedes (forward)
    (r"\b(?:precedes?|comes\s+before)\b", "precedes", False),
    # "produces / generates" → produces (forward)
    (r"\b(?:produces?|generates?|outputs?)\b", "produces", False),
    # "configured in" → configured_in
    (r"\b(?:configured?\s+in|set\s+up\s+in)\b", "configured_in", False),
    # "configures" → configures
    (r"\b(?:configures?)\b", "configures", False),
    # "deployed on" → deployed_on
    (r"\b(?:deployed?\s+on)\b", "deployed_on", False),
    # "forked from" → forked_from
    (r"\b(?:forked?\s+from)\b", "forked_from", False),
    # "derived from" → derived_from
    (r"\b(?:derived?\s+from)\b", "derived_from", False),
    # "inspired by" → inspired_by
    (r"\b(?:inspired?\s+by)\b", "inspired_by", False),
    # "alternate to" → alternate_to
    (r"\b(?:alternate?\s+to|alternative\s+to)\b", "alternate_to", False),
    # "based on" → based_on
    (r"\b(?:based\s+on)\b", "based_on", False),
    # "aligns with" → aligns_with
    (r"\b(?:aligns?\s+with)\b", "aligns_with", False),
]

# NL noun phrases → node type filters
NL_TYPE_MAP: List[Tuple[str, str]] = [
    (r"\b(?:tools?|software|apps?|applications?|programs?|libraries?|frameworks?)\b", "tool"),
    (r"\b(?:people?|person|who|users?|developers?|team|guys?)\b", "person"),
    (r"\b(?:projects?|initiatives?|endeavors?)\b", "project"),
    (r"\b(?:systems?|services?|infrastructure|platforms?)\b", "system"),
    (r"\b(?:concepts?|ideas?|notions?|topics?)\b", "concept"),
    (r"\b(?:places?|locations?|where|servers?|machines?)\b", "place"),
    (r"\b(?:organizations?|companies?|teams?|groups?)\b", "organization"),
    (r"\b(?:files?|documents?|pages?|notes?|articles?)\b", "file"),
    (r"\b(?:skills?|abilities?|expertise?)\b", "skill"),
    (r"\b(?:media|images?|videos?|audio|music|songs?|tracks?)\b", "media"),
    (r"\b(?:events?|happenings?|occurrences?)\b", "event"),
    (r"\b(?:facts?|truths?|known?)\b", "fact"),
    (r"\b(?:decisions?|choices?|resolutions?)\b", "decision"),
    (r"\b(?:preferences?|likes?|favorites?)\b", "preference"),
]

# Temporal patterns
TEMPORAL_RE = re.compile(
    r"(?:before|after|since|until|at)\s+"
    r"(\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:T\d{1,2}:\d{2})?|"
    r"today|yesterday|last\s+\w+|this\s+\w+)",
    re.IGNORECASE,
)

# Stop words for entity extraction
STOP_WORDS = {
    "what", "is", "are", "the", "a", "an", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "and", "or", "does", "do", "can", "how",
    "many", "much", "all", "list", "show", "tell", "give", "me", "find",
    "get", "know", "about", "that", "this", "these", "those", "it", "its",
    "they", "them", "their", "we", "our", "you", "your", "i", "my",
}


# ===================================================================
# Entity Resolver
# ===================================================================


class EntityResolver:
    """Resolve natural language entity names to graph node IDs."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def resolve(self, name: str, type_filter: str = "") -> List[Dict[str, Any]]:
        """Resolve a name to graph node(s) via fuzzy matching.

        Matches against node label and ID, preferring exact matches, then
        substring, then word-boundary matching.

        Args:
            name: Entity name from NL query (e.g. 'Hermes', 'Konan').
            type_filter: Optional node type to restrict to.

        Returns:
            List of matching nodes with id, label, type, score.
        """
        if not name or not name.strip():
            return []

        name = name.strip()
        results: List[Dict[str, Any]] = []

        # 1. Exact match on label
        if type_filter:
            rows = self._conn.execute(
                "SELECT id, type, label, codex FROM nodes WHERE LOWER(label) = LOWER(?) AND type = ? LIMIT 5",
                (name, type_filter),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, type, label, codex FROM nodes WHERE LOWER(label) = LOWER(?) LIMIT 5",
                (name,),
            ).fetchall()
        for r in rows:
            results.append({"id": r[0], "label": r[2], "type": r[1], "codex": r[3] or "", "score": 1.0})

        if results:
            return results

        # 2. Substring match on label
        if type_filter:
            rows = self._conn.execute(
                "SELECT id, type, label, codex FROM nodes WHERE LOWER(label) LIKE ? AND type = ? LIMIT 10",
                (f"%{name.lower()}%", type_filter),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, type, label, codex FROM nodes WHERE LOWER(label) LIKE ? LIMIT 10",
                (f"%{name.lower()}%",),
            ).fetchall()
        for r in rows:
            label = r[2]
            score = round(len(name) / max(len(label), 1), 2) if label else 0.3
            results.append({"id": r[0], "label": label, "type": r[1], "codex": r[3] or "", "score": score})

        if results:
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:5]

        # 3. Word-boundary match on ID (entity:name patterns)
        search_term = name.lower().replace(" ", "-").replace("_", "-")
        if type_filter:
            rows = self._conn.execute(
                "SELECT id, type, label, codex FROM nodes WHERE LOWER(id) LIKE ? AND type = ? LIMIT 10",
                (f"%{search_term}%", type_filter),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, type, label, codex FROM nodes WHERE LOWER(id) LIKE ? LIMIT 10",
                (f"%{search_term}%",),
            ).fetchall()
        for r in rows:
            results.append({"id": r[0], "label": r[2], "type": r[1], "codex": r[3] or "", "score": 0.5})

        return results[:5]

    def resolve_exact(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Resolve a known node ID to its details."""
        row = self._conn.execute(
            "SELECT id, type, label, codex FROM nodes WHERE id = ?",
            (node_id,),
        ).fetchone()
        if row:
            return {"id": row[0], "label": row[2], "type": row[1], "codex": row[3] or ""}
        return None


# ===================================================================
# Multi-hop Walker
# ===================================================================


class MultiHopWalker:
    """Breadth-first graph traversal with configurable depth and filters."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def walk(
        self,
        start_ids: List[str],
        edge_types: List[str],
        reverse: bool = False,
        target_types: Optional[List[str]] = None,
        max_hops: int = 2,
        max_results: int = 50,
        soft_type_filter: bool = True,
    ) -> List[Dict[str, Any]]:
        """Walk the graph from starting nodes, following specified edges.

        Uses breadth-first search up to `max_hops` depth.

        Args:
            start_ids: Starting node IDs.
            edge_types: Edge types to traverse (e.g. ['uses', 'contains']).
            reverse: If True, traverse edges in reverse direction.
            target_types: Preferred node types. When soft_type_filter=True
                          (default), results matching these types are boosted
                          but non-matching results are still included.
            max_hops: Maximum traversal depth.
            max_results: Cap on returned results.
            soft_type_filter: If True (default), target_types is a preference.
                              If False, target_types is a hard filter.

        Returns:
            List of paths.
        """
        if not start_ids or not edge_types:
            return []

        visited: Set[str] = set(start_ids)
        results: List[Dict[str, Any]] = []
        # Each frontier entry: (current_node_id, path_so_far, depth)
        frontier: List[Tuple[str, List[str], int]] = [
            (nid, [nid], 0) for nid in start_ids
        ]

        edge_placeholders = ",".join("?" for _ in edge_types)

        while frontier and len(results) < max_results:
            new_frontier: List[Tuple[str, List[str], int]] = []

            for current_id, path, depth in frontier:
                if depth >= max_hops:
                    continue

                # Build query based on direction
                if reverse:
                    query = f"""
                        SELECT e.type, e.weight,
                               src.id AS other_id, src.label AS other_label,
                               src.type AS other_type
                        FROM edges e
                        JOIN nodes src ON e.source_id = src.id
                        WHERE e.target_id = ?
                          AND e.type IN ({edge_placeholders})
                    """
                    params: List[Any] = [current_id, *edge_types]
                else:
                    query = f"""
                        SELECT e.type, e.weight,
                               tgt.id AS other_id, tgt.label AS other_label,
                               tgt.type AS other_type
                        FROM edges e
                        JOIN nodes tgt ON e.target_id = tgt.id
                        WHERE e.source_id = ?
                          AND e.type IN ({edge_placeholders})
                    """
                    params = [current_id, *edge_types]

                rows = self._conn.execute(query, params).fetchall()

                for row in rows:
                    edge_type = row[0]
                    weight = row[1]
                    other_id = row[2]
                    other_label = row[3] or other_id
                    other_type = row[4]

                    if other_id in visited:
                        continue

                    visited.add(other_id)

                    # Apply target type filter
                    if target_types:
                        if not soft_type_filter and other_type not in target_types:
                            continue
                        # With soft filter, we still collect but note the match
                        type_match = other_type in target_types
                    else:
                        type_match = True

                    new_path = path + [f"--{edge_type}-->", other_id]
                    hop_result = {
                        "path": new_path,
                        "depth": depth + 1,
                        "edge_type": edge_type,
                        "weight": weight,
                        "node_id": other_id,
                        "node_label": other_label,
                        "node_type": other_type,
                        "type_match": type_match,
                    }
                    results.append(hop_result)

                    if depth + 1 < max_hops:
                        new_frontier.append((other_id, [other_id], depth + 1))

            frontier = new_frontier

        return results[:max_results]

    def walk_chain(
        self,
        start_ids: List[str],
        chain: List[Dict[str, Any]],
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Walk a chain of relations sequentially.

        Each step in the chain specifies edge_types and optional target_types.
        Step N's results become Step N+1's starting nodes.

        Args:
            start_ids: Starting node IDs.
            chain: List of steps:
                   [{'edge_types': ['uses'], 'reverse': False, 'target_types': ['tool']},
                    {'edge_types': ['runs_on'], 'reverse': False}]
            max_results: Cap on results.

        Returns:
            List of final paths from the last step.
        """
        current_ids = start_ids
        all_results: List[Dict[str, Any]] = []

        for step_idx, step in enumerate(chain):
            edge_types = step.get("edge_types", [])
            reverse = step.get("reverse", False)
            target_types = step.get("target_types")

            results = self.walk(
                start_ids=current_ids,
                edge_types=edge_types,
                reverse=reverse,
                target_types=target_types,
                max_hops=1,  # One hop per chain step
                max_results=max_results,
            )

            if not results:
                return []

            # Collect unique node IDs for next step
            current_ids = list(set(r["node_id"] for r in results))

            if step_idx == len(chain) - 1:
                # Last step — return these results
                all_results = results
            else:
                # Intermediate step — just update frontier
                pass

        return all_results


# ===================================================================
# NL Query Parser
# ===================================================================


def parse_nl_query(query: str) -> Dict[str, Any]:
    """Parse a natural language graph query into structured components.

    Extracts: anchor entity, relation verb, target type, temporal constraints.

    Examples:
        "What tools does Hermes use?"
        → {'anchor': 'Hermes', 'relations': ['uses'], 'target_types': ['tool']}

        "What systems does Konan own?"
        → {'anchor': 'Konan', 'relations': ['owned_by'], 'target_types': ['system']}

        "Who created Pantheon?"
        → {'anchor': 'Pantheon', 'relations': ['created_by'], 'reverse': True}

    Returns:
        Dict with: anchor, relations, target_types, reverse, temporal.
    """
    result: Dict[str, Any] = {
        "anchor": "",
        "relations": [],
        "target_types": [],
        "reverse": False,
        "temporal": {},
        "confidence": 0.0,
    }

    if not query or not query.strip():
        return result

    cleaned = query.strip()

    # ── Extract target type nouns ──────────────────────────────────
    target_types: List[str] = []
    for pattern, ntype in NL_TYPE_MAP:
        if re.search(pattern, cleaned, re.IGNORECASE):
            target_types.append(ntype)
    result["target_types"] = target_types

    # ── Extract relation verb → edge types ─────────────────────────
    relations: List[str] = []
    reverse = False
    for pattern, edge_type, is_reverse in NL_RELATION_MAP:
        if re.search(pattern, cleaned, re.IGNORECASE):
            relations.append(edge_type)
            if is_reverse:
                reverse = True
            break  # First match only (avoid over-matching)

    # If no explicit relation, try implicit ones from common patterns
    if not relations:
        # "X and Y" → no relation needed, just show connections
        # "X" → just show what X is connected to
        pass

    result["relations"] = relations
    result["reverse"] = reverse

    # ── Extract anchor entity ──────────────────────────────────────
    # Remove query words (what, is, are, the, etc.), target type words,
    # and relation words. The remaining noun is the anchor.

    # First, remove the target type words
    remaining = cleaned
    for pattern, _ in NL_TYPE_MAP:
        remaining = re.sub(pattern, "", remaining, flags=re.IGNORECASE)

    # Remove relation words
    for pattern, _, _ in NL_RELATION_MAP:
        remaining = re.sub(pattern, "", remaining, flags=re.IGNORECASE)

    # Remove question words and common filler
    remaining = re.sub(
        r"\b(?:what|is|are|the|a|an|does|do|can|how|list|show|tell|give|me|find|get|know|that|this|all|about|please)\b",
        "",
        remaining,
        flags=re.IGNORECASE,
    )

    # Remove punctuation, clean whitespace
    remaining = re.sub(r"[?.,!;:()\"']", "", remaining)
    remaining = re.sub(r"\s+", " ", remaining).strip()

    # The remaining words should be the anchor entity
    # Also try matching common multi-word entities
    if remaining:
        result["anchor"] = remaining
        result["confidence"] = 0.7

    # ── Temporal operators ─────────────────────────────────────────
    temporal_match = TEMPORAL_RE.search(cleaned)
    if temporal_match:
        result["temporal"] = {"operator": temporal_match.group(0).split()[0], "value": temporal_match.group(1)}

    return result


# ===================================================================
# Graph Query Engine
# ===================================================================


class GraphQueryEngine:
    """Main engine: NL query → multi-hop graph traversal → formatted results."""

    def __init__(self):
        self._conn: Optional[sqlite3.Connection] = None

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(_GRAPH_DB))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def query(
        self,
        nl_query: str,
        hops: int = 0,
        max_results: int = 30,
        output_format: str = "json",
    ) -> Any:
        """Execute a natural language graph query.

        Args:
            nl_query: Natural language question (e.g. "What tools does Hermes use?").
            hops: Max traversal depth (0=auto: 1 for specific relations, 2 for exploration).
            max_results: Max results to return.
            output_format: 'json' or 'markdown'.

        Returns:
            JSON dict or formatted markdown.
        """
        conn = self._connect()

        # Step 1: Parse the NL query
        parsed = parse_nl_query(nl_query)
        anchor_name = parsed["anchor"]
        relations = parsed["relations"]
        target_types = parsed["target_types"]
        reverse = parsed["reverse"]

        if not anchor_name:
            return self._empty_result(nl_query, "Could not identify anchor entity in query")

        # Step 2: Resolve anchor entity
        resolver = EntityResolver(conn)
        entities = resolver.resolve(anchor_name)

        if not entities:
            return self._empty_result(nl_query, f"Could not find entity '{anchor_name}' in knowledge graph")

        # Auto-resolve hop count: 0 means 1 for specific relations, 2 for exploration
        if hops == 0:
            hops = 1 if relations else 2

        # Step 3: Walk the graph
        walker = MultiHopWalker(conn)
        start_ids = [e["id"] for e in entities]

        if relations:
            # We have a specific relation — follow it
            results = walker.walk(
                start_ids=start_ids,
                edge_types=relations,
                reverse=reverse,
                target_types=target_types if target_types else None,
                max_hops=hops,
                max_results=max_results,
                soft_type_filter=True,
            )
        else:
            # No explicit relation — show all direct connections
            # Get all edge types connected to the anchor
            all_edge_types = [
                r[0]
                for r in conn.execute(
                    "SELECT DISTINCT type FROM edges WHERE source_id IN ({}) OR target_id IN ({}) LIMIT 30".format(
                        ",".join("?" for _ in start_ids),
                        ",".join("?" for _ in start_ids),
                    ),
                    start_ids + start_ids,
                ).fetchall()
            ]

            results = walker.walk(
                start_ids=start_ids,
                edge_types=all_edge_types[:10],  # Top 10 most common
                reverse=False,
                target_types=target_types if target_types else None,
                max_hops=min(hops, 2),
                max_results=max_results,
            )

            if not results and target_types:
                # Try reverse
                results = walker.walk(
                    start_ids=start_ids,
                    edge_types=all_edge_types[:10],
                    reverse=True,
                    target_types=target_types if target_types else None,
                    max_hops=min(hops, 2),
                    max_results=max_results,
                )

        # Step 4: Format results
        if not results:
            # Try without type filter as fallback (graph node types often don't match NL expectations)
            if target_types:
                fallback = walker.walk(
                    start_ids=start_ids,
                    edge_types=relations or [],
                    reverse=reverse,
                    target_types=None,
                    max_hops=hops,
                    max_results=max_results,
                    soft_type_filter=False,
                )
                if fallback:
                    results = fallback

        if not results:
            return self._empty_result(
                nl_query,
                f"No connections found for '{anchor_name}'"
                + (f" via {relations}" if relations else "")
                + (f" of type {target_types}" if target_types else ""),
            )

        # Sort: type matches first, then by weight descending
        results.sort(key=lambda r: (r.get("type_match", True), -(r.get("weight", 0))))

        # Enrich with labels for path display
        enriched = []
        for r in results:
            r["anchor_label"] = entities[0]["label"]
            r["anchor_id"] = entities[0]["id"]
            r["anchor_type"] = entities[0]["type"]

            # Get full path with labels
            nodes_in_path = [entities[0]]
            # If path has more than just start node, get labels for the end
            nodes_in_path.append({
                "id": r["node_id"],
                "label": r["node_label"],
                "type": r["node_type"],
            })
            r["nodes"] = nodes_in_path
            enriched.append(r)

        conn.close()

        if output_format == "json":
            return {
                "query": nl_query,
                "parsed": parsed,
                "anchor": entities[0],
                "alternate_matches": entities[1:] if len(entities) > 1 else [],
                "results": enriched,
                "total": len(enriched),
            }

        # ── Markdown ──────────────────────────────────────────────
        return self._format_markdown(nl_query, parsed, entities, enriched)

    def _empty_result(self, query: str, reason: str) -> Dict[str, Any]:
        return {
            "query": query,
            "error": reason,
            "results": [],
            "total": 0,
        }

    def _format_markdown(
        self,
        query: str,
        parsed: Dict[str, Any],
        entities: List[Dict[str, Any]],
        results: List[Dict[str, Any]],
    ) -> str:
        """Format results as readable markdown."""
        lines: List[str] = []
        lines.append(f"## 🔗 Graph Query: `{query}`")
        lines.append("")

        # Parsed explanation
        anchor_label = entities[0]["label"] if entities else parsed.get("anchor", "?")
        rel_str = ", ".join(parsed.get("relations", [])) or "any relation"
        type_str = ", ".join(parsed.get("target_types", [])) or "any type"
        lines.append(f"**Anchor:** {anchor_label} · **Relation:** {rel_str} · **Target:** {type_str}")
        lines.append("")

        if len(entities) > 1:
            lines.append(f"ℹ️ Multiple matches for '{parsed.get('anchor', '')}':")
            for e in entities:
                lines.append(f"  - {e['label']} ({e['type']}, score: {e.get('score', 0):.2f})")
            lines.append("")

        lines.append(f"**{len(results)} result(s):**")
        lines.append("")

        # Group by edge type
        by_edge: Dict[str, List[Dict]] = {}
        for r in results:
            et = r.get("edge_type", "unknown")
            if et not in by_edge:
                by_edge[et] = []
            by_edge[et].append(r)

        dir_label = "←" if parsed.get("reverse") else "→"
        for edge_type, items in sorted(by_edge.items(), key=lambda x: len(x[1]), reverse=True):
            lines.append(f"### {anchor_label} {dir_label} `{edge_type}` ({len(items)})")
            lines.append("")
            for item in items[:15]:
                label = item.get("node_label", item.get("node_id", "?"))
                ntype = item.get("node_type", "")
                weight = item.get("weight", 0)
                lines.append(f"- **{label}** ({ntype}, weight: {weight:.2f})")
            if len(items) > 15:
                lines.append(f"  *... and {len(items) - 15} more*")
            lines.append("")

        lines.append(f"---")
        lines.append(f"_Query: `{query}` · Depth: {parsed.get('hops', 2)} · {len(results)} results_")
        return "\n".join(lines)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


# ===================================================================
# Alternative: Direct NL → Multi-hop Chain
# ===================================================================


def parse_chain_query(nl_query: str) -> List[Dict[str, Any]]:
    """Parse a multi-step chain query into a sequence of hops.

    Example:
        "What tools does Hermes use, and what do those tools run on?"
        → [
            {'edge_types': ['uses'], 'target_types': ['tool']},
            {'edge_types': ['runs_on']}
          ]

    For now, returns a simple 1-hop chain. Future: parse "and then" patterns.
    """
    parsed = parse_nl_query(nl_query)
    chain = [
        {
            "edge_types": parsed["relations"] or ["uses", "contains", "runs_on", "part_of"],
            "reverse": parsed["reverse"],
            "target_types": parsed["target_types"] if parsed["target_types"] else None,
        }
    ]
    return chain


# ===================================================================
# CLI entry point
# ===================================================================


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Ichor Graph Query — multi-hop NL queries on the Pantheon knowledge graph"
    )
    parser.add_argument("query", nargs="?", default="", help='NL query (e.g. "What tools does Hermes use?")')
    parser.add_argument("--hops", "-H", type=int, default=0, help="Max traversal hops (0=auto)")
    parser.add_argument("--limit", "-l", type=int, default=30, help="Max results")
    parser.add_argument("--markdown", "-d", action="store_true", help="Output markdown instead of JSON")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")

    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    engine = GraphQueryEngine()

    if args.interactive:
        print("🔗 Ichor Graph Query — Interactive mode")
        print("Type queries or 'quit' to exit.\n")
        while True:
            try:
                q = input("query> ").strip()
                if q.lower() in ("quit", "exit", "q"):
                    break
                if not q:
                    continue
                result = engine.query(q, hops=args.hops, max_results=args.limit, output_format="markdown")
                print(f"\n{result}\n")
            except KeyboardInterrupt:
                print()
                break
            except Exception as e:
                print(f"Error: {e}")
    elif args.query:
        result = engine.query(
            args.query,
            hops=args.hops,
            max_results=args.limit,
            output_format="markdown" if args.markdown else "json",
        )
        if args.markdown:
            print(result)
        else:
            print(json.dumps(result, indent=2, default=str))
    else:
        parser.print_help()

    engine.close()


if __name__ == "__main__":
    main()
