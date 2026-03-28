"""
services/fraud_detector.py
==========================
Nine rule-based fraud pattern detectors covering the most important
mule-account signals.

Detectors
---------
1. circular         — money cycles back to the origin account
2. high_frequency   — burst of many transfers in a short rolling window
3. fan_out          — one sender → many receivers quickly (dispersal)
4. fan_in           — many senders → one receiver quickly (aggregation)
5. smurfing         — many small transfers that collectively exceed a threshold
6. round_trip       — funds leave and return to the same account within 24 h
7. rapid_sequence   — transactions spaced only seconds apart (bot activity)
8. high_degree_hub  — connected to an abnormally large number of peers
9. repeated_cycle   — the same circular-flow pattern appears multiple times

All detectors annotate the NetworkX nodes they flag with pattern tags,
which are later used for scoring and explainability.
"""

import logging
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Dict, List, Set

import networkx as nx
import pandas as pd

logger = logging.getLogger("fraudlink.fraud_detector")

# ── Tunable thresholds ─────────────────────────────────────────────────────
CYCLE_MAX_LEN             = 6      # hops: longer cycles are ignored
FREQ_WINDOW_MIN           = 60     # rolling window width (minutes)
FREQ_TX_THRESHOLD         = 5      # min tx in window → high_frequency
FAN_OUT_MIN_RECEIVERS     = 4      # unique receivers in window → fan_out
FAN_IN_MIN_SENDERS        = 4      # unique senders in window → fan_in
SMURF_CEILING             = 9_999  # each transfer stays below this
SMURF_AGGREGATE           = 40_000 # combined total exceeds this
SMURF_MIN_TX              = 5      # minimum transfer count
ROUND_TRIP_HOURS          = 24     # send + receive gap ≤ this
RAPID_GAP_SECONDS         = 10     # gap between consecutive tx (seconds)
RAPID_MIN_COUNT           = 3      # min rapid-gap events to flag
HIGH_DEGREE_MULTIPLIER    = 3.0    # flag if degree > mean * this factor
REPEATED_CYCLE_MIN        = 2      # how many times a cycle must repeat


class FraudDetector:

    def detect_all(
        self,
        G:  nx.MultiDiGraph,
        df: pd.DataFrame,
    ) -> Dict[str, List[str]]:
        """
        Run all nine detectors.

        Returns
        -------
        dict mapping pattern_name → [account_id, …]

        Side-effect: annotates every flagged NetworkX node with its pattern tags.
        """
        patterns: Dict[str, List[str]] = {
            "circular":        self.detect_circular(G),
            "high_frequency":  self.detect_high_frequency(df),
            "fan_out":         self.detect_fan_out(df),
            "fan_in":          self.detect_fan_in(df),
            "smurfing":        self.detect_smurfing(df),
            "round_trip":      self.detect_round_trip(G, df),
            "rapid_sequence":  self.detect_rapid_sequence(df),
            "high_degree_hub": self.detect_high_degree_hubs(G),
            "repeated_cycle":  self.detect_repeated_cycles(G),
        }

        self._annotate_nodes(G, patterns)

        total = sum(len(v) for v in patterns.values())
        logger.info(
            "Pattern detection complete — total flags: %d | %s",
            total,
            {k: len(v) for k, v in patterns.items()},
        )
        return patterns

    # ── Detector 1: Circular transactions ─────────────────────────────────

    def detect_circular(self, G: nx.MultiDiGraph) -> List[str]:
        """
        Find all simple cycles up to CYCLE_MAX_LEN hops.
        Every account that appears in at least one cycle is flagged.
        """
        flagged: Set[str] = set()
        try:
            simple_G = nx.DiGraph(G)   # collapse parallel edges for cycle search
            for cycle in nx.simple_cycles(simple_G):
                if len(cycle) <= CYCLE_MAX_LEN:
                    flagged.update(cycle)
        except Exception as exc:
            logger.warning("Cycle detection error: %s", exc)
        return list(flagged)

    # ── Detector 2: High-frequency burst ──────────────────────────────────

    def detect_high_frequency(self, df: pd.DataFrame) -> List[str]:
        """
        Flag senders who sent ≥ FREQ_TX_THRESHOLD transactions within
        any FREQ_WINDOW_MIN-minute sliding window.
        """
        flagged: Set[str] = set()
        window  = timedelta(minutes=FREQ_WINDOW_MIN)
        df_s    = df.sort_values("timestamp")

        for sender, grp in df_s.groupby("sender"):
            times = grp["timestamp"].sort_values().tolist()
            for i, t0 in enumerate(times):
                count = sum(1 for t in times[i:] if (t - t0) <= window)
                if count >= FREQ_TX_THRESHOLD:
                    flagged.add(str(sender))
                    break

        return list(flagged)

    # ── Detector 3: Fan-out (dispersal) ───────────────────────────────────

    def detect_fan_out(self, df: pd.DataFrame) -> List[str]:
        """
        Flag senders who reach ≥ FAN_OUT_MIN_RECEIVERS unique recipients
        within a single rolling window.
        """
        flagged: Set[str] = set()
        window  = timedelta(minutes=FREQ_WINDOW_MIN)
        df_s    = df.sort_values("timestamp")

        for sender, grp in df_s.groupby("sender"):
            times  = grp["timestamp"].tolist()
            recvrs = grp["receiver"].tolist()
            for i, t0 in enumerate(times):
                unique = {
                    str(recvrs[i + j])
                    for j, t in enumerate(times[i:])
                    if (t - t0) <= window
                }
                if len(unique) >= FAN_OUT_MIN_RECEIVERS:
                    flagged.add(str(sender))
                    break

        return list(flagged)

    # ── Detector 4: Fan-in (aggregation) ──────────────────────────────────

    def detect_fan_in(self, df: pd.DataFrame) -> List[str]:
        """
        Flag receivers that collect from ≥ FAN_IN_MIN_SENDERS unique
        senders within a single rolling window.
        """
        flagged: Set[str] = set()
        window  = timedelta(minutes=FREQ_WINDOW_MIN)
        df_s    = df.sort_values("timestamp")

        for receiver, grp in df_s.groupby("receiver"):
            times   = grp["timestamp"].tolist()
            senders = grp["sender"].tolist()
            for i, t0 in enumerate(times):
                unique = {
                    str(senders[i + j])
                    for j, t in enumerate(times[i:])
                    if (t - t0) <= window
                }
                if len(unique) >= FAN_IN_MIN_SENDERS:
                    flagged.add(str(receiver))
                    break

        return list(flagged)

    # ── Detector 5: Smurfing / structuring ────────────────────────────────

    def detect_smurfing(self, df: pd.DataFrame) -> List[str]:
        """
        Flag senders whose individual transfers all stay below SMURF_CEILING
        but whose combined total exceeds SMURF_AGGREGATE with at least
        SMURF_MIN_TX transfers (classic structuring to avoid reporting).
        """
        flagged: Set[str] = set()
        for sender, grp in df.groupby("sender"):
            small = grp[grp["amount"] < SMURF_CEILING]
            if (
                len(small) >= SMURF_MIN_TX
                and small["amount"].sum() >= SMURF_AGGREGATE
            ):
                flagged.add(str(sender))
        return list(flagged)

    # ── Detector 6: Round-trip flow ────────────────────────────────────────

    def detect_round_trip(
        self, G: nx.MultiDiGraph, df: pd.DataFrame
    ) -> List[str]:
        """
        Flag accounts that both send and receive money within ROUND_TRIP_HOURS
        via different paths (wash-trading / layering).
        """
        flagged: Set[str] = set()
        window  = timedelta(hours=ROUND_TRIP_HOURS)
        df_s    = df.sort_values("timestamp")
        simple_G = nx.DiGraph(G)

        last_sent:  Dict[str, pd.Timestamp] = {}
        last_recvd: Dict[str, pd.Timestamp] = {}

        for _, row in df_s.iterrows():
            s, r, t = str(row["sender"]), str(row["receiver"]), row["timestamp"]
            last_sent[s]  = t
            last_recvd[r] = t

        for acct in G.nodes:
            if acct not in last_sent or acct not in last_recvd:
                continue
            gap = abs(last_recvd[acct] - last_sent[acct])
            if gap <= window and not simple_G.has_edge(acct, acct):
                flagged.add(acct)

        return list(flagged)

    # ── Detector 7: Rapid-sequence transactions ────────────────────────────

    def detect_rapid_sequence(self, df: pd.DataFrame) -> List[str]:
        """
        Flag senders with at least RAPID_MIN_COUNT consecutive transactions
        spaced ≤ RAPID_GAP_SECONDS seconds apart (bot / automated behaviour).
        """
        flagged: Set[str] = set()
        gap_threshold = timedelta(seconds=RAPID_GAP_SECONDS)
        df_s = df.sort_values("timestamp")

        for sender, grp in df_s.groupby("sender"):
            times = grp["timestamp"].sort_values().tolist()
            if len(times) < RAPID_MIN_COUNT:
                continue
            rapid_count = 0
            for i in range(1, len(times)):
                diff = times[i] - times[i - 1]
                if diff <= gap_threshold:
                    rapid_count += 1
                    if rapid_count >= RAPID_MIN_COUNT - 1:
                        flagged.add(str(sender))
                        break
                else:
                    rapid_count = 0

        return list(flagged)

    # ── Detector 8: High-degree hub ────────────────────────────────────────

    def detect_high_degree_hubs(self, G: nx.MultiDiGraph) -> List[str]:
        """
        Flag accounts whose total degree exceeds the network mean by
        a factor of HIGH_DEGREE_MULTIPLIER.
        """
        if G.number_of_nodes() < 3:
            return []

        degrees = dict(G.degree())
        mean_deg = sum(degrees.values()) / len(degrees)
        threshold = mean_deg * HIGH_DEGREE_MULTIPLIER

        return [n for n, d in degrees.items() if d > threshold]

    # ── Detector 9: Repeated circular flow ─────────────────────────────────

    def detect_repeated_cycles(self, G: nx.MultiDiGraph) -> List[str]:
        """
        Flag accounts that appear in the same circular flow pattern
        at least REPEATED_CYCLE_MIN times across all detected cycles.

        Works by normalising each cycle to a frozenset and counting
        how many times each account appears in repeated cycles.
        """
        flagged: Set[str] = set()
        try:
            simple_G = nx.DiGraph(G)
            cycle_sets: Counter = Counter()

            for cycle in nx.simple_cycles(simple_G):
                if len(cycle) <= CYCLE_MAX_LEN:
                    cycle_sets[frozenset(cycle)] += 1

            repeated = {
                node
                for cycle_key, count in cycle_sets.items()
                if count >= REPEATED_CYCLE_MIN
                for node in cycle_key
            }
            flagged.update(repeated)
        except Exception as exc:
            logger.warning("Repeated cycle detection error: %s", exc)

        return list(flagged)

    # ── Node annotation ────────────────────────────────────────────────────

    def _annotate_nodes(
        self,
        G:        nx.MultiDiGraph,
        patterns: Dict[str, List[str]],
    ):
        """Write pattern labels onto each flagged NetworkX node (additive)."""
        for pattern_name, account_list in patterns.items():
            for acct in account_list:
                if acct in G.nodes:
                    existing = set(G.nodes[acct].get("patterns", []))
                    existing.add(pattern_name)
                    G.nodes[acct]["patterns"] = list(existing)


# ── Module-level singleton ─────────────────────────────────────────────────
fraud_detector = FraudDetector()