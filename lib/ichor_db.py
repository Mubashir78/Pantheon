"""Ichor Memory Engine — Database Layer.

Manages the SQLite-backed events database with FTS5 full-text search.
All event storage, retrieval, and search operations for the Pantheon system.
"""

import os
import sqlite3
from typing import Any, Optional


class IchorDB:
    """Manages the Ichor events database connection and operations.

    Provides CRUD operations for ichor_events and FTS5 full-text search,
    with automatic schema initialization on first connect.
    """

    def __init__(self, db_path: str = "~/.hermes/ichor.db"):
        """Initialize the Ichor database manager.

        Args:
            db_path: Path to the SQLite database file. Tilde is expanded
                     to the user's home directory. Defaults to ~/.hermes/ichor.db.
        """
        self.db_path = os.path.expanduser(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Open (or create) the database and ensure the schema exists.

        Returns:
            The active sqlite3.Connection object.

        Raises:
            sqlite3.Error: If the database cannot be opened or schema creation fails.
        """
        if self._conn is not None:
            return self._conn

        # Ensure parent directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._conn.row_factory = sqlite3.Row

        # Load and execute the schema DDL
        schema_path = os.path.join(
            os.path.dirname(__file__), "..", "schemas", "ichor-events.sql"
        )
        schema_path = os.path.normpath(schema_path)

        with open(schema_path, "r") as f:
            schema_sql = f.read()
        self._conn.executescript(schema_sql)
        self._conn.commit()

        return self._conn

    def insert_event(
        self,
        session_id: str,
        event_type: str,
        subject: str,
        predicate: Optional[str] = None,
        object: Optional[str] = None,
        confidence: float = 0.8,
        source: Optional[str] = None,
        raw_text: Optional[str] = None,
        god_name: Optional[str] = None,
        direction: Optional[str] = None,
        peer_god: Optional[str] = None,
    ) -> int:
        """Insert a new event into the database.

        Args:
            session_id: Identifier for the source god session.
            event_type: One of 'decision', 'commitment', 'preference', 'fact', 'correction'.
            subject: The subject of the event (who or what the event is about).
            predicate: Optional relationship/predicate describing the event.
            object: Optional object of the relationship.
            confidence: Confidence score (0.0 to 1.0). Default 0.8.
            source: Origin tier — 'tier_a', 'tier_b', or 'manual'.
            raw_text: Original raw text the event was extracted from.
            god_name: Name of the god that generated this event.
            direction: Optional 'user→agent', 'agent→user', 'agent→agent', etc.
            peer_god: Optional peer god name for cross-god events.

        Returns:
            The row ID of the newly inserted event.

        Raises:
            sqlite3.Error: If the insert fails.
        """
        conn = self.connect()
        # Dynamic column list — include direction/peer_god if provided
        columns = [
            "session_id", "event_type", "subject", "predicate", "object",
            "confidence", "source", "raw_text", "god_name",
        ]
        values = [
            session_id, event_type, subject, predicate, object,
            confidence, source, raw_text, god_name,
        ]
        if direction is not None:
            columns.append("direction")
            values.append(direction)
        if peer_god is not None:
            columns.append("peer_god")
            values.append(peer_god)

        placeholders = ", ".join("?" * len(columns))
        col_list = ", ".join(columns)
        cursor = conn.execute(
            f"INSERT INTO ichor_events ({col_list}) VALUES ({placeholders})",
            values,
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def query_fts(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Full-text search across events using FTS5.

        Performs a search on subject, predicate, object, and raw_text fields.

        Args:
            query: FTS5 search query string (supports FTS5 syntax like phrase matching).
            limit: Maximum number of results to return. Default 10.

        Returns:
            List of event dictionaries matching the search query.
        """
        conn = self.connect()
        cursor = conn.execute(
            """
            SELECT e.*
            FROM ichor_events e
            JOIN ichor_events_fts fts ON e.id = fts.rowid
            WHERE ichor_events_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def query_by_session(self, session_id: str) -> list[dict[str, Any]]:
        """Retrieve all events for a given session.

        Args:
            session_id: The session identifier to look up.

        Returns:
            List of event dictionaries for the specified session,
            ordered by creation time.
        """
        conn = self.connect()
        cursor = conn.execute(
            """
            SELECT * FROM ichor_events
            WHERE session_id = ?
            ORDER BY created_at ASC
            """,
            (session_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def query_by_type(self, event_type: str, limit: int = 50) -> list[dict[str, Any]]:
        """Filter events by type.

        Args:
            event_type: One of 'decision', 'commitment', 'preference', 'fact', 'correction'.
            limit: Maximum number of results to return. Default 50.

        Returns:
            List of event dictionaries matching the type.
        """
        conn = self.connect()
        cursor = conn.execute(
            """
            SELECT * FROM ichor_events
            WHERE event_type = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (event_type, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get the most recent events.

        Args:
            limit: Maximum number of results to return. Default 20.

        Returns:
            List of the most recent event dictionaries.
        """
        conn = self.connect()
        cursor = conn.execute(
            """
            SELECT * FROM ichor_events
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def count(self) -> int:
        """Return the total number of events in the database.

        Returns:
            Total event count.
        """
        conn = self.connect()
        cursor = conn.execute("SELECT COUNT(*) AS cnt FROM ichor_events")
        row = cursor.fetchone()
        return row["cnt"] if row else 0

    def close(self) -> None:
        """Close the database connection if it is open."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
