"""
dialectic_ai/memory/sqlite_graph.py

DIALECTICAL DESCRIPTION:
  Origin: KnowledgeGraph lives in RAM. PersistentMemory saves it in JSON, 
    which causes concurrency issues and does not allow for complex queries.
  Contradiction: We want long-term memory, but saving the entire JSON graph 
    every time the agent sneezes (update) is an O(N) operation that breaks with growth.
  Resolution: The Knowledge Graph is moved to a relational structure (SQLite). Concepts
    and relationships become rows in tables. Updates occur atomically in O(1).
  Outcome: The ability to run a swarm of agents (Multi-Agent) that can simultaneously
    read and write to a single Knowledge Graph without data loss.
  Own contradictions: SQLite can be locked during too intense writing.
    No built-in vector semantics (need to connect sqlite-vss).
"""
import sqlite3
import json
from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.schema import AgentInput, MemoryUpdate
from dialectic_ai.memory.base import BaseMemory

@dialectical(
    origin="PersistentMemory (JSON) does not support atomicity and concurrent access of a swarm of agents.",
    contradiction="Saving the full graph every time is O(N). This does not scale for enterprise.",
    resolves="Moves the storage of the graph to a relational SQLite model. Updates in O(1), atomicity.",
    generates="Enterprise-ready long-term memory. Agents can sleep for years and work in parallel.",
    own_contradictions="Requires schema migrations. Less flexible than schema-less JSON. SQLite can lock up.",
    layer=1,
)
class SQLiteKnowledgeGraphMemory(BaseMemory):
    """
    Persistent agent memory based on SQLite.
    Stores the graph of concepts and statuses atomically in a .db file.
    """
    def __init__(self, db_path: str = "agent_memory.db"):
        super().__init__()
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS concepts (
                    concept TEXT PRIMARY KEY,
                    status TEXT,
                    details TEXT
                )
            ''')
            conn.commit()

    def update(self, updates: list[MemoryUpdate]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for update in updates:
                cursor.execute('''
                    INSERT INTO concepts (concept, status, details)
                    VALUES (?, ?, ?)
                    ON CONFLICT(concept) DO UPDATE SET
                        status=excluded.status,
                        details=excluded.details
                ''', (update.concept, update.status, update.details))
            conn.commit()

    def process_turn(self, user_input: AgentInput, parsed_response: dict) -> None:
        updates = [
            MemoryUpdate(
                concept=u.get("concept", ""),
                status=u.get("status", "unknown"),
                details=u.get("details", "")
            )
            for u in parsed_response.get("knowledge_updates", [])
            if u.get("concept")
        ]
        if updates:
            self.update(updates)

    def get_context(self) -> str:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT concept, status, details FROM concepts")
            rows = cursor.fetchall()
            
        if not rows:
            return "The knowledge graph is currently empty."
            
        context = "Current User Knowledge Graph:\n"
        for row in rows:
            context += f"- {row[0]} [{row[1]}]: {row[2]}\n"
        return context

    def clear(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM concepts")
            conn.commit()
