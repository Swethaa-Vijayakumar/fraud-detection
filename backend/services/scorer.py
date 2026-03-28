"""
services/scorer.py
==================
Computes a final composite risk score (0–100) per account by blending
four independent signals:

  Signal                    Weight   Notes
  ─────────────────────────  ──────  ──────────────────────────────────────
  Base score                 10 pts  Every account starts with 10
  Rule-based patterns        up to 50 pts  weighted sum of detected patterns
  ML anomaly (IsolationForest) up to 40 pts  scaled 0-40
  Network centrality         up to 20 pts  degree / asymmetry heuristic

Raw total is clipped to [0, 100].

Score bands
  0–39   LOW     — normal
  40–69  MEDIUM  — investigate
  70–100 HIGH    — flag / block
"""

import logging
from typing import Dict, List, Optional

import networkx as nx
import pandas as pd

logger = logging.getLogger("fraudlink.scorer")

# ── Pattern weights ────────────────────────────────────────────────────────
# Each pattern adds this many raw points to the rule signal.
PATTERN_WEIGHTS: Dict[str, float] = {
    "circular":        35.0,
    "smurfing":        30.0,
    "repeated_cycle":  30.0,
    "rapid_sequence":  28.0,
    "high_frequency":  25.0,
    "round_trip":      25.0,
    "fan_out":         20.0,
    "fan_in":          20.0,
    "high_degree_hub": 15.0,
}
PATTERN_CAP  = 50.0   # rule signal is capped at this
ML_MAX       = 40.0   # ML signal contributes at most this many points
NETWORK_MAX  = 20.0   # network signal contributes at most this many points
BASE_SCORE   = 10.0   # every account starts here


class Scorer:
    """Computes and caches composite risk scores."""

    def __init__(self):
        self._scores: Dict[str, float] = {}

    # ── Public API ─────────────────────────────────────────────────────────

    def compute(
        self,
        patterns:       Dict[str, List[str]],
        anomaly_scores: Dict[str, float],
        G:              nx.MultiDiGraph,
        df:             pd.DataFrame,
    ) -> Dict[str, float]:
        """
        Compute and cache a final score for every account in the graph.

        Parameters
        ----------
        patterns       : output of FraudDetector.detect_all()
        anomaly_scores : output of AnomalyClassifier.fit_predict()  (0-100)
        G              : NetworkX transaction graph
        df             : raw transaction DataFrame

        Returns
        -------
        dict { account_id: float (0-100) }
        """
        accounts = list(G.nodes)

        rule_scores    = self._rule_signal(patterns, accounts)
        network_scores = self._network_signal(G, accounts)

        final: Dict[str, float] = {}
        for acct in accounts:
            r = rule_scores.get(acct, 0.0)          # 0-50
            m = anomaly_scores.get(acct, 50.0)       # 0-100 raw → scale to 0-40
            n = network_scores.get(acct, 0.0)        # 0-20

            ml_contribution = (m / 100.0) * ML_MAX   # scale 0-40

            total = BASE_SCORE + r + ml_contribution + n
            total = round(max(0.0, min(100.0, total)), 2)
            final[acct] = total

            # Write back to graph node
            if acct in G.nodes:
                G.nodes[acct]["riskScore"]    = total
                G.nodes[acct]["anomaly_score"] = round(m, 2)

        self._scores = final

        logger.info(
            "Scoring complete — %d accounts | HIGH: %d | MEDIUM: %d | LOW: %d",
            len(final),
            sum(1 for s in final.values() if s >= 70),
            sum(1 for s in final.values() if 40 <= s < 70),
            sum(1 for s in final.values() if s < 40),
        )
        return final

    def get_all_scores(self) -> Dict[str, float]:
        """Return the cached score dict from the most recent compute() call."""
        return self._scores

    def get_score(self, account_id: str) -> Optional[float]:
        return self._scores.get(account_id)

    # ── Private ────────────────────────────────────────────────────────────

    def _rule_signal(
        self,
        patterns: Dict[str, List[str]],
        accounts: List[str],
    ) -> Dict[str, float]:
        """
        Sum weighted pattern contributions per account, capped at PATTERN_CAP.

        Example: circular (35) + high_frequency (25) = 60 → capped at 50.
        """
        scores: Dict[str, float] = {a: 0.0 for a in accounts}
        for pattern_name, flagged in patterns.items():
            weight = PATTERN_WEIGHTS.get(pattern_name, 10.0)
            for acct in flagged:
                if acct in scores:
                    scores[acct] = min(scores[acct] + weight, PATTERN_CAP)
        return scores

    def _network_signal(
        self,
        G:        nx.MultiDiGraph,
        accounts: List[str],
    ) -> Dict[str, float]:
        """
        Heuristic 0-NETWORK_MAX score based on:
          • Normalised total degree  (high degree → hub behaviour)
          • Degree asymmetry penalty (very skewed in/out → suspicious)
        """
        if G.number_of_nodes() == 0:
            return {}

        max_degree = max((G.degree(n) for n in G.nodes), default=1)
        scores: Dict[str, float] = {}

        for acct in accounts:
            d_in  = G.in_degree(acct)
            d_out = G.out_degree(acct)
            total = d_in + d_out

            deg_norm  = total / max(max_degree, 1)                     # 0-1
            asymmetry = (max(d_in, d_out) / total - 0.5) * 2 if total > 0 else 0  # 0-1

            raw = (deg_norm * 0.6 + asymmetry * 0.4) * NETWORK_MAX
            scores[acct] = round(min(raw, NETWORK_MAX), 2)

        return scores


# ── Module-level singleton ─────────────────────────────────────────────────
scorer = Scorer()