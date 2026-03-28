import logging
from typing import Any, Dict, List

logger = logging.getLogger("fraudlink.neo4j")


class Neo4jService:
    """Thread-safe singleton wrapper around Neo4j driver."""

    def __init__(self):
        self._driver = None
        self._connected = False

    # ── Lifecycle ─────────────────────────────────────────

    def connect(self):
        from neo4j import GraphDatabase

        # 🔥 HARD CODE (temporary fix)
        uri = "bolt://localhost:7687"
        user = "neo4j"
        password = "12345678"   # 👈 ensure same as Neo4j login

        try:
            self._driver = GraphDatabase.driver(
                uri,
                auth=(user, password)
            )

            # check connection
            self._driver.verify_connectivity()

            self._connected = True
            logger.info("✅ Connected to Neo4j successfully")

        except Exception as e:
            self._connected = False
            logger.error(f"❌ Neo4j connection failed: {e}")
            raise e

    def close(self):
        if self._driver:
            self._driver.close()
            self._connected = False
            logger.info("Neo4j connection closed")

    def is_connected(self) -> bool:
        return self._connected

    # ── Query execution ───────────────────────────────────

    def run(self, query: str, **params) -> List[Dict[str, Any]]:
        if not self._connected:
            return []

        with self._driver.session() as session:
            result = session.run(query, **params)
            return [dict(r) for r in result]

    def run_write(self, query: str, **params) -> List[Dict[str, Any]]:
        if not self._connected:
            return []

        def _tx(tx):
            return [dict(r) for r in tx.run(query, **params)]

        with self._driver.session() as session:
            return session.execute_write(_tx)

    # ── Schema ────────────────────────────────────────────

    def create_indexes(self):
        if not self._connected:
            return

        queries = [
            "CREATE CONSTRAINT account_id_unique IF NOT EXISTS FOR (a:Account) REQUIRE a.id IS UNIQUE",
            "CREATE INDEX account_risk_idx IF NOT EXISTS FOR (a:Account) ON (a.riskScore)"
        ]

        for q in queries:
            try:
                self.run_write(q)
            except Exception as e:
                logger.debug(f"Skipped index: {e}")

        logger.info("Indexes created / verified")


# singleton
neo4j_service = Neo4jService()