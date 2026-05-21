"""Ichor Tier A — Zero-LLM Regex Extraction Engine.

Fires on compaction events (configurable threshold, default 40%).
Extracts structured events from conversation text using compiled regex patterns.
Events are stored in the ichor_events table via IchorDB for instant FTS5 search.

Usage:
    extractor = TierAExtractor()
    count = extractor.extract_and_store(text, session_id, god_name="apollo")
"""

import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from lib.ichor_db import IchorDB
from lib.ichor_patterns import PATTERNS, EVENT_TYPE_META, ALL_TYPES

logger = logging.getLogger("ichor_tier_a")

# Events below this confidence are discarded
CONFIDENCE_FLOOR = 0.5

# Default path for the Ichor database
ICHOR_DB_PATH = os.path.expanduser("~/.hermes/ichor.db")

# Default path for the graph database
GRAPH_DB_PATH = os.path.expanduser("~/.hermes/pantheon/graph.db")


def _ensure_gods_path() -> None:
    """Add ~/pantheon/pantheon-core/ to sys.path so GraphClient is importable."""
    gods_path = str(Path.home() / "pantheon" / "pantheon-core")
    if gods_path not in sys.path:
        sys.path.insert(0, gods_path)


class TierAExtractor:
    """Zero-LLM regex extraction engine. Fires on compaction events.

    Extracts decisions, commitments, facts, preferences, corrections,
    insights, blockers, references, and follow-ups from conversation text.
    """

    def __init__(self, db: Optional[IchorDB] = None, db_path: str = "",
                 graph_db_path: str = ""):
        """Initialize with optional existing IchorDB connection.

        Args:
            db: Existing IchorDB instance. If None, creates one.
            db_path: Path to ichor.db. Defaults to ~/.hermes/ichor.db.
            graph_db_path: Path to graph.db. Defaults to ~/.hermes/pantheon/graph.db.
        """
        if db is not None:
            self.db = db
        else:
            path = db_path or ICHOR_DB_PATH
            self.db = IchorDB(db_path=path)
        self.db.connect()
        self._graph_path = graph_db_path or GRAPH_DB_PATH
        self._graph_client = None

    # ── Core extraction ──────────────────────────────────────────────────

    def extract_from_text(
        self,
        text: str,
        session_id: str,
        god_name: str = "",
        speaker: str = "",
    ) -> List[Dict]:
        """Extract events from a single text segment.

        Args:
            text: Raw conversation text to scan.
            session_id: Current session identifier.
            god_name: Name of the god processing this text.
            speaker: 'user' or 'assistant' — affects confidence baseline.

        Returns:
            List of event dicts with confidence >= CONFIDENCE_FLOOR.
        """
        if not text or not text.strip():
            return []

        results: List[Dict] = []
        seen: Dict[Tuple[str, str], Dict] = {}  # (event_type, subject) -> event

        # User messages get higher baseline confidence
        baseline = 0.9 if speaker.lower() in ("user", "human", "") else 0.6

        for event_type in ALL_TYPES:
            patterns = PATTERNS.get(event_type, [])
            meta = EVENT_TYPE_META.get(event_type, {})
            type_baseline = meta.get("baseline_confidence", 0.7)

            for pattern in patterns:
                for match in pattern.finditer(text):
                    self._process_match(
                        match=match,
                        event_type=event_type,
                        text=text,
                        baseline=baseline,
                        type_baseline=type_baseline,
                        speaker=speaker,
                        session_id=session_id,
                        god_name=god_name,
                        results=results,
                        seen=seen,
                    )

        return results

    def _process_match(
        self,
        match: re.Match,
        event_type: str,
        text: str,
        baseline: float,
        type_baseline: float,
        speaker: str,
        session_id: str,
        god_name: str,
        results: List[Dict],
        seen: Dict,
    ) -> None:
        """Process a single regex match into an event if it passes confidence."""
        matched_text = match.group(0).strip()

        # Calculate confidence
        confidence = (baseline + type_baseline) / 2

        # Bonus for user-originated exact-ish matches
        if speaker.lower() in ("user", "human", ""):
            confidence += 0.05

        # Penalty for very short matches (likely noise)
        if len(matched_text) < 6:
            confidence -= 0.15

        confidence = max(0.1, min(round(confidence, 2), 1.0))

        if confidence < CONFIDENCE_FLOOR:
            return

        # Extract surrounding context
        context = _extract_context(text, match.start(), match.end())

        # Extract subject noun phrase before the match
        subject = _extract_subject(text, match.start(), match.end())

        # Dedup: same (event_type, subject) gets merged with confidence boost
        dedup_key = (event_type, subject.lower() if subject else matched_text.lower())
        if dedup_key in seen:
            existing = seen[dedup_key]
            existing["confidence"] = min(existing["confidence"] + 0.05, 1.0)
            existing["occurrences"] = existing.get("occurrences", 1) + 1
            return

        event = {
            "event_type": event_type,
            "subject": subject or matched_text,
            "predicate": event_type,
            "object": matched_text,
            "confidence": confidence,
            "raw_text": context[:300],
            "speaker": speaker,
            "session_id": session_id,
            "god_name": god_name,
            "occurrences": 1,
        }
        seen[dedup_key] = event
        results.append(event)

    # ── Segment-level extraction ─────────────────────────────────────────

    def extract_from_segment(
        self,
        user_msg: str,
        assistant_msg: str,
        session_id: str,
        god_name: str = "",
    ) -> List[Dict]:
        """Extract from a user+assistant exchange pair.

        User messages get higher baseline confidence.
        """
        results: List[Dict] = []
        seen: Dict = {}

        # User messages
        for ev in self.extract_from_text(
            user_msg, session_id, god_name, speaker="user"
        ):
            key = (ev["event_type"], ev["subject"].lower())
            if key not in seen:
                seen[key] = ev
                results.append(ev)

        # Assistant messages
        for ev in self.extract_from_text(
            assistant_msg, session_id, god_name, speaker="assistant"
        ):
            key = (ev["event_type"], ev["subject"].lower())
            if key not in seen:
                seen[key] = ev
                results.append(ev)

        return results

    # ── Store extraction results ─────────────────────────────────────────

    def extract_and_store(
        self,
        text: str,
        session_id: str,
        god_name: str = "",
        speaker: str = "",
    ) -> int:
        """Extract from text + insert into ichor_events table.

        Args:
            text: Conversation text to scan.
            session_id: Current session identifier.
            god_name: Name of the god.
            speaker: 'user' or 'assistant'.

        Returns:
            Number of events stored.
        """
        events = self.extract_from_text(text, session_id, god_name, speaker)
        return self._store_events(events, session_id, god_name)

    def extract_and_store_segment(
        self,
        user_msg: str,
        assistant_msg: str,
        session_id: str,
        god_name: str = "",
    ) -> int:
        """Extract from user+assistant exchange + store in ichor_events.

        Returns:
            Number of events stored.
        """
        events = self.extract_from_segment(
            user_msg, assistant_msg, session_id, god_name
        )
        return self._store_events(events, session_id, god_name)

    def _store_events(
        self,
        events: List[Dict],
        session_id: str,
        god_name: str = "",
    ) -> int:
        """Store a list of extracted events in the database and sync to graph."""
        count = 0
        for ev in events:
            try:
                self.db.insert_event(
                    session_id=session_id,
                    event_type=ev["event_type"],
                    subject=ev["subject"],
                    predicate=ev.get("predicate", ev["event_type"]),
                    object=ev.get("object", ""),
                    confidence=ev["confidence"],
                    source="tier_a",
                    raw_text=ev.get("raw_text", ""),
                    god_name=god_name or ev.get("god_name", ""),
                )
                count += 1
            except Exception as e:
                logger.warning("Failed to store event: %s", e)

        # Sync extracted entities to the knowledge graph (zero-LLM)
        try:
            graph_count = self._sync_events_to_graph(events, session_id, god_name)
            if graph_count:
                logger.debug(
                    "Graph sync: %d entities written for session %s",
                    graph_count, session_id[:8],
                )
        except Exception as e:
            logger.debug("Graph sync failed (non-fatal): %s", e)

        return count

    # ── Graph sync ─────────────────────────────────────────────────────

    def _get_graph_client(self):
        """Lazy-initialize and return the GraphClient instance."""
        if self._graph_client is None:
            try:
                _ensure_gods_path()
                from gods.graph_client import GraphClient  # noqa: PLC0415
                gc = GraphClient(db_path=self._graph_path)
                gc.connect()
                self._graph_client = gc
                logger.info("GraphClient connected at %s", self._graph_path)
            except Exception as exc:
                logger.debug("GraphClient init failed (non-fatal): %s", exc)
                self._graph_client = False  # sentinel — don't retry
        return self._graph_client if self._graph_client else None

    def _sync_events_to_graph(
        self,
        events: List[Dict],
        session_id: str,
        god_name: str = "",
    ) -> int:
        """Write extracted entities and relationships to the graph database.

        For each unique subject in the extracted events:
          1. Registers the subject as an entity node in the graph.
          2. Registers the session node.
          3. Creates a 'references' edge from session → entity.

        Returns the number of graph nodes created/updated.
        """
        gc = self._get_graph_client()
        if gc is None:
            return 0

        count = 0
        seen_subjects: Set[str] = set()

        # Collect unique subjects with sufficient confidence
        for ev in events:
            subject = ev.get("subject", "").strip()
            confidence = ev.get("confidence", 0.0)
            if not subject or confidence < CONFIDENCE_FLOOR:
                continue
            key = subject.lower()
            if key in seen_subjects:
                continue
            seen_subjects.add(key)

            codex = ""
            if god_name:
                codex = f"Codex-{god_name}"

            try:
                # Register entity node
                gc.register_entity(subject, codex=codex)
                count += 1
            except Exception as exc:
                logger.debug("Graph register_entity failed for '%s': %s", subject, exc)

        # Register session node and link to entities
        if seen_subjects and session_id:
            try:
                session_node = gc.register_session(
                    session_id,
                    metadata={"god": god_name} if god_name else {},
                )
                for subject in seen_subjects:
                    slug = subject.lower().replace(" ", "-").replace("'", "")[:60]
                    entity_id = f"entity:{slug}"
                    try:
                        gc.add_edge(session_node, entity_id, "references", weight=0.8)
                    except Exception as exc:
                        logger.debug("Graph add_edge failed: %s", exc)
            except Exception as exc:
                logger.debug("Graph session registration failed: %s", exc)

        # Sync FTS index for new nodes
        try:
            if gc._conn:
                gc._conn.commit()
        except Exception:
            pass

        return count

    # ── Close ────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the database connection."""
        self.db.close()


# ── Helper functions ───────────────────────────────────────────────────


def _extract_context(text: str, match_start: int, match_end: int) -> str:
    """Extract surrounding context around a match."""
    start = max(0, match_start - 80)
    end = min(len(text), match_end + 80)
    context = text[start:end].strip()
    return context


def _extract_subject(text: str, match_start: int, match_end: int) -> str:
    """Extract the likely subject noun phrase before the match.

    Walks backward from the match to find the subject of the sentence.
    """
    before = text[:match_start].strip()
    if not before:
        return ""

    # Find last sentence boundary before the match
    sentence_breaks = [i for i, c in enumerate(before) if c in ".!?"]
    if sentence_breaks:
        before = before[sentence_breaks[-1] + 1 :].strip()

    # Take last 3-5 meaningful words as subject context
    words = before.split()
    if len(words) > 5:
        words = words[-5:]

    # Filter out stop words at the end
    stop_words = {
        "the", "a", "an", "to", "for", "of", "in", "on", "at",
        "is", "was", "are", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did",
        "will", "would", "could", "should", "may", "might",
        "and", "or", "but", "if", "so", "then", "that",
        "this", "it", "we", "i", "you", "they", "he", "she",
    }
    while words and words[-1].lower() in stop_words:
        words = words[:-1]

    if words:
        return " ".join(words)
    return ""


def create_extractor(db_path: str = "") -> TierAExtractor:
    """Convenience factory for creating a TierAExtractor."""
    return TierAExtractor(db_path=db_path)
