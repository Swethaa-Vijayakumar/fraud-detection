"""
routers/scores.py
=================
Returns fraud risk scores for all accounts, with explainability.

Endpoints
---------
GET /api/v1/scores          — full ranked list
GET /api/v1/scores/summary  — distribution summary
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from services.graph_builder import graph_builder
from services.scorer import scorer

logger = logging.getLogger("fraudlink.scores")
router = APIRouter()


def _band(score: float) -> str:
    """Convert a numeric score to a human-readable risk band."""
    if score >= 70:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"


def _explain(account_id: str, score: float) -> list[str]:
    """
    Generate human-readable explanations for why an account has its score.
    Pulls pattern tags from the graph node attributes.
    """
    reasons = []
    patterns = graph_builder.get_node_patterns(account_id)

    pattern_explanations = {
        "circular":        "Participates in circular money flow (laundering loop)",
        "high_frequency":  "Sends many transactions in rapid succession (burst behaviour)",
        "fan_out":         "Disperses funds to many receivers quickly (mule hub)",
        "fan_in":          "Collects funds from many senders (aggregation point)",
        "smurfing":        "Multiple sub-threshold transfers that sum to a large amount",
        "round_trip":      "Funds leave and return to this account via a different path",
        "rapid_sequence":  "Transactions spaced only seconds apart (automated activity)",
        "high_degree_hub": "Connected to an abnormally large number of accounts",
        "repeated_cycle":  "Involved in the same circular flow pattern more than once",
    }

    for p in patterns:
        if p in pattern_explanations:
            reasons.append(pattern_explanations[p])

    if score >= 70 and not reasons:
        reasons.append("ML model identified anomalous transaction behaviour")
    elif score >= 40 and not reasons:
        reasons.append("Elevated network centrality compared to peer accounts")

    return reasons


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get(
    "/scores",
    summary="Get risk scores for all accounts",
    response_description="Ranked list of accounts with scores and explanations",
)
def get_scores(
    min_score:    float = Query(0.0,   description="Minimum score to include (0–100)"),
    limit:        int   = Query(200,   description="Max records to return"),
    order:        str   = Query("desc", description="Sort order: asc | desc"),
    flagged_only: bool  = Query(False,  description="Only return HIGH-risk accounts"),
):
    """
    Returns every account's fraud risk score together with:

    - **risk_band** — LOW / MEDIUM / HIGH
    - **patterns**  — rule-based signals detected
    - **explanation** — plain-English reasons for the score
    - **anomaly_score** — raw IsolationForest output (0–100)

    Score bands:

    | Range  | Band   |
    |--------|--------|
    | 0–39   | LOW    |
    | 40–69  | MEDIUM |
    | 70–100 | HIGH   |
    """
    try:
        risk_scores = scorer.get_all_scores()
        if not risk_scores:
            g = graph_builder.get_graph()
            if g is None or g.number_of_nodes() == 0:
                return {"message": "No data — POST to /ingest first.", "accounts": []}

        results = []
        for acct, score in risk_scores.items():
            if score < min_score:
                continue
            if flagged_only and score < 70:
                continue

            node_data = {}
            g = graph_builder.get_graph()
            if g and acct in g.nodes:
                node_data = g.nodes[acct]

            results.append({
                "account_id":    acct,
                "risk_score":    round(score, 2),
                "risk_band":     _band(score),
                "flagged":       score >= 70,
                "patterns":      node_data.get("patterns", []),
                "anomaly_score": node_data.get("anomaly_score"),
                "explanation":   _explain(acct, score),
            })

        reverse = order.lower() != "asc"
        results.sort(key=lambda x: x["risk_score"], reverse=reverse)
        return {"total": len(results), "accounts": results[:limit]}

    except Exception as exc:
        logger.exception("Scores endpoint failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/scores/summary", summary="Risk score distribution summary")
def scores_summary():
    """Top-10 riskiest accounts and band-level counts."""
    risk_scores = scorer.get_all_scores()
    if not risk_scores:
        return {"message": "No data — POST to /ingest first."}

    values = list(risk_scores.values())
    top10  = sorted(risk_scores.items(), key=lambda x: -x[1])[:10]

    return {
        "total_accounts": len(values),
        "band_counts": {
            "high":   sum(1 for s in values if s >= 70),
            "medium": sum(1 for s in values if 40 <= s < 70),
            "low":    sum(1 for s in values if s < 40),
        },
        "mean_score": round(sum(values) / len(values), 2),
        "max_score":  round(max(values), 2),
        "top_10_risky": [
            {"account_id": a, "risk_score": round(s, 2), "explanation": _explain(a, s)}
            for a, s in top10
        ],
    }