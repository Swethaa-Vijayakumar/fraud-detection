"""
ml/feature_extractor.py
=======================
Computes per-account graph features that are fed into the IsolationForest.

Features (15 total)
-------------------
Graph topology
  degree_in              incoming edge count
  degree_out             outgoing edge count
  degree_total           sum of in + out
  degree_centrality      normalised degree centrality
  in_degree_centrality   normalised in-degree centrality
  out_degree_centrality  normalised out-degree centrality
  betweenness_centrality fraction of shortest paths through this node
  clustering_coeff       clustering coefficient (triangle density)
  pagerank               PageRank score

Transaction statistics
  total_sent             cumulative amount sent
  total_received         cumulative amount received
  net_flow               total_received − total_sent
  avg_tx_amount          mean amount per sent transaction
  tx_count               total transactions (sent + received)
  unique_counterparties  unique trading partners (senders + receivers)
"""

import logging
from typing import Optional

import networkx as nx
import numpy as np
import pandas as pd

logger = logging.getLogger("fraudlink.features")


class FeatureExtractor:

    # Ordered feature list used by the classifier
    FEATURE_COLS = [
        "degree_in",
        "degree_out",
        "degree_total",
        "degree_centrality",
        "in_degree_centrality",
        "out_degree_centrality",
        "betweenness_centrality",
        "clustering_coeff",
        "pagerank",
        "total_sent",
        "total_received",
        "net_flow",
        "avg_tx_amount",
        "tx_count",
        "unique_counterparties",
    ]

    def extract(self, G: nx.MultiDiGraph, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute all features for every account node in G.

        Parameters
        ----------
        G  : NetworkX MultiDiGraph from graph_builder.build()
        df : raw transaction DataFrame

        Returns
        -------
        pd.DataFrame — index = account_id, columns = FEATURE_COLS
                        Empty DataFrame if the graph has no nodes.
        """
        if G is None or G.number_of_nodes() == 0:
            logger.warning("Empty graph — skipping feature extraction.")
            return pd.DataFrame()

        logger.info("Extracting features for %d accounts …", G.number_of_nodes())

        # ── Graph-topology measures ───────────────────────────────────────
        # Centrality functions need a simple DiGraph (no parallel edges)
        simple_G = nx.DiGraph(G)

        deg_centrality     = self._safe(nx.degree_centrality,     simple_G)
        in_deg_centrality  = self._safe(nx.in_degree_centrality,  simple_G)
        out_deg_centrality = self._safe(nx.out_degree_centrality, simple_G)
        betweenness        = self._safe(
            nx.betweenness_centrality, simple_G, normalized=True
        )
        clustering         = self._safe(
            nx.clustering, simple_G.to_undirected()
        )
        pagerank           = self._safe(
            nx.pagerank, simple_G, alpha=0.85, max_iter=200
        )

        # ── Transaction statistics ────────────────────────────────────────
        sent_agg = (
            df.groupby("sender")
              .agg(total_sent=("amount", "sum"),
                   tx_sent=("amount", "count"),
                   avg_amount=("amount", "mean"))
              .rename_axis("account")
        )
        recv_agg = (
            df.groupby("receiver")
              .agg(total_received=("amount", "sum"),
                   tx_recv=("amount", "count"))
              .rename_axis("account")
        )
        uniq_recv = df.groupby("sender")["receiver"].nunique().rename("uniq_recv")
        uniq_send = df.groupby("receiver")["sender"].nunique().rename("uniq_send")

        # ── Assemble one row per account ──────────────────────────────────
        rows = []
        for node in G.nodes:
            d_in  = G.in_degree(node)
            d_out = G.out_degree(node)

            s_sent     = float(sent_agg.loc[node, "total_sent"])  if node in sent_agg.index else 0.0
            s_recv     = float(recv_agg.loc[node, "total_received"]) if node in recv_agg.index else 0.0
            tx_sent_n  = int(sent_agg.loc[node, "tx_sent"])   if node in sent_agg.index else 0
            tx_recv_n  = int(recv_agg.loc[node, "tx_recv"])   if node in recv_agg.index else 0
            avg_amt    = float(sent_agg.loc[node, "avg_amount"]) if node in sent_agg.index else 0.0

            rows.append({
                "account_id":             node,
                "degree_in":              d_in,
                "degree_out":             d_out,
                "degree_total":           d_in + d_out,
                "degree_centrality":      deg_centrality.get(node, 0.0),
                "in_degree_centrality":   in_deg_centrality.get(node, 0.0),
                "out_degree_centrality":  out_deg_centrality.get(node, 0.0),
                "betweenness_centrality": betweenness.get(node, 0.0),
                "clustering_coeff":       clustering.get(node, 0.0),
                "pagerank":               pagerank.get(node, 0.0),
                "total_sent":             s_sent,
                "total_received":         s_recv,
                "net_flow":               s_recv - s_sent,
                "avg_tx_amount":          avg_amt,
                "tx_count":               tx_sent_n + tx_recv_n,
                "unique_counterparties":  int(uniq_recv.get(node, 0)) + int(uniq_send.get(node, 0)),
            })

        feature_df = (
            pd.DataFrame(rows)
              .set_index("account_id")
              .fillna(0)
              .replace([np.inf, -np.inf], 0)
        )

        logger.info(
            "Features ready: %d accounts × %d features",
            len(feature_df), len(feature_df.columns),
        )
        return feature_df

    # ── Helper ─────────────────────────────────────────────────────────────

    @staticmethod
    def _safe(func, *args, **kwargs) -> dict:
        """
        Call a NetworkX function safely.
        Returns an empty dict on any exception so extraction continues.
        """
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            logger.debug("NetworkX function '%s' failed: %s", func.__name__, exc)
            return {}


# ── Module-level singleton ─────────────────────────────────────────────────
feature_extractor = FeatureExtractor()