"""
services/graph_builder.py
=========================
Converts a raw transaction DataFrame into:

1. An **in-memory NetworkX MultiDiGraph** — used by all analysis modules.
2. **Neo4j Account nodes + TRANSFER relationships** — persisted when available.

The cached graph is rebuilt on each /ingest call.
"""

import logging
import uuid
from typing import Dict, List, Optional

import networkx as nx
import pandas as pd

from services.neo4j_service import neo4j_service

logger = logging.getLogger("fraudlink.graph_builder")

# Simple channel inference from amount ranges
# Replace with a real "channel" CSV column if your data has one.
_CHANNEL_RULES = [
    (0,          5_000,         "UPI"),
    (5_000,      50_000,        "Digital Wallet"),
    (50_000,     500_000,       "Online Banking"),
    (500_000,    float("inf"),  "Bank Wire"),
]


def _infer_channel(amount: float) -> str:
    for lo, hi, ch in _CHANNEL_RULES:
        if lo <= amount < hi:
            return ch
    return "Bank Wire"


class GraphBuilder:
    """Builds and caches the transaction graph for the current session."""

    def __init__(self):
        self._graph: Optional[nx.MultiDiGraph] = None

    # ── Public API ─────────────────────────────────────────────────────────

    def build(self, df: pd.DataFrame) -> nx.MultiDiGraph:
        """
        Parse `df` and (re)build the in-memory and Neo4j graphs.

        Parameters
        ----------
        df : DataFrame — must have columns sender, receiver, amount, timestamp

        Returns
        -------
        nx.MultiDiGraph — the freshly constructed graph
        """
        logger.info("Building graph from %d transactions …", len(df))

        # MultiDiGraph allows multiple parallel edges (several transfers between
        # the same pair of accounts on the same day, for example).
        G = nx.MultiDiGraph()

        for _, row in df.iterrows():
            sender    = str(row["sender"]).strip()
            receiver  = str(row["receiver"]).strip()
            amount    = float(row.get("amount", 0))
            timestamp = row.get("timestamp", pd.Timestamp.now())
            channel   = str(row.get("channel", _infer_channel(amount)))
            tx_id     = str(row.get("tx_id", uuid.uuid4().hex[:12]))

            # Ensure nodes exist with default attributes
            for nid in (sender, receiver):
                if nid not in G:
                    G.add_node(nid, riskScore=0.0, patterns=[], anomaly_score=None)

            # Add directed edge
            G.add_edge(
                sender, receiver,
                amount=amount,
                timestamp=timestamp,
                channel=channel,
                txId=tx_id,
            )

            # Persist to Neo4j (no-op when not connected)
            self._persist(sender, receiver, amount, timestamp, channel, tx_id)

        self._graph = G
        logger.info(
            "Graph built: %d accounts, %d edges",
            G.number_of_nodes(), G.number_of_edges(),
        )
        return G

    def get_graph(self) -> Optional[nx.MultiDiGraph]:
        """Return the cached graph, or None if build() has not been called."""
        return self._graph

    def get_node_patterns(self, account_id: str) -> List[str]:
        """Return the fraud pattern tags on a node."""
        if self._graph is None or account_id not in self._graph.nodes:
            return []
        return self._graph.nodes[account_id].get("patterns", [])

    def persist_scores(self, risk_scores: Dict[str, float]):
        """Write final risk scores to both the NetworkX node attrs and Neo4j."""
        if self._graph is None:
            return
        for acct, score in risk_scores.items():
            if acct in self._graph.nodes:
                self._graph.nodes[acct]["riskScore"] = score
            patterns = self.get_node_patterns(acct)
            try:
                neo4j_service.persist_risk_score(acct, score, patterns)
            except Exception as exc:
                logger.debug("Neo4j score persist skipped: %s", exc)

    def tag_patterns(self, account_id: str, new_patterns: List[str]):
        """
        Attach fraud pattern labels to a node's attribute list.
        Existing labels are preserved (set union, no duplicates).
        """
        if self._graph is not None and account_id in self._graph.nodes:
            existing = set(self._graph.nodes[account_id].get("patterns", []))
            self._graph.nodes[account_id]["patterns"] = list(existing | set(new_patterns))

    def set_anomaly_score(self, account_id: str, score: float):
        """Store the ML anomaly score on the node for the accounts endpoint."""
        if self._graph is not None and account_id in self._graph.nodes:
            self._graph.nodes[account_id]["anomaly_score"] = score

    # ── Private ────────────────────────────────────────────────────────────

    def _persist(
        self,
        sender:    str,
        receiver:  str,
        amount:    float,
        timestamp,
        channel:   str,
        tx_id:     str,
    ):
        """Write a single transaction to Neo4j (silent no-op on failure)."""
        try:
            neo4j_service.upsert_account(sender,   {"id": sender})
            neo4j_service.upsert_account(receiver, {"id": receiver})
            neo4j_service.upsert_transfer(
                sender, receiver,
                {
                    "txId":      tx_id,
                    "amount":    amount,
                    "timestamp": str(timestamp),
                    "channel":   channel,
                },
            )
        except Exception as exc:
            logger.debug("Neo4j persist skipped for %s→%s: %s", sender, receiver, exc)


# ── Module-level singleton ─────────────────────────────────────────────────
graph_builder = GraphBuilder()