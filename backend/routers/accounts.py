"""
routers/accounts.py
===================
Full account profile: risk score, patterns, explanation, transactions,
neighbours and aggregate stats.

Endpoints
---------
GET /api/v1/account/{account_id}  — single account detail
GET /api/v1/accounts              — list all accounts (lightweight)
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from services.graph_builder import graph_builder
from services.scorer import scorer

logger = logging.getLogger("fraudlink.accounts")
router = APIRouter()


def _band(score: float) -> str:
    if score >= 70:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"


def _build_explanation(patterns: list, score: float, stats: dict) -> dict:
    """
    Return a structured explainability object describing *why* an account
    has its risk score — designed for rendering in a UI explanation panel.
    """
    flags = []

    # Pattern-level explanations
    explanations = {
        "circular":        {
            "title":   "Circular Money Flow",
            "detail":  "This account is part of a transaction loop where funds "
                       "return to the origin, a classic money-laundering indicator.",
            "weight":  "HIGH",
        },
        "high_frequency":  {
            "title":   "Burst Transactions",
            "detail":  "Sent an abnormally high number of transfers within a "
                       "short rolling window, suggesting automated or scripted behaviour.",
            "weight":  "HIGH",
        },
        "fan_out":         {
            "title":   "Fund Dispersal (Fan-Out)",
            "detail":  "Rapidly distributed funds to many different receivers — "
                       "a hallmark of mule-hub accounts used to layer illicit money.",
            "weight":  "MEDIUM",
        },
        "fan_in":          {
            "title":   "Fund Aggregation (Fan-In)",
            "detail":  "Collected funds from many different senders in a short "
                       "window, indicating a collection point in a mule network.",
            "weight":  "MEDIUM",
        },
        "smurfing":        {
            "title":   "Structuring / Smurfing",
            "detail":  "Multiple individually sub-threshold transfers whose "
                       "combined total is large — used to evade reporting limits.",
            "weight":  "HIGH",
        },
        "round_trip":      {
            "title":   "Round-Trip Flow",
            "detail":  "Funds leave this account and return via a different path "
                       "within 24 hours — indicative of wash-trading or layering.",
            "weight":  "MEDIUM",
        },
        "rapid_sequence":  {
            "title":   "Rapid-Fire Transactions",
            "detail":  "Several transactions were spaced only seconds apart, "
                       "consistent with automated payment scripts.",
            "weight":  "HIGH",
        },
        "high_degree_hub": {
            "title":   "High-Degree Hub",
            "detail":  "This account is connected to an unusually large number "
                       "of peers, placing it at the centre of the fraud network.",
            "weight":  "MEDIUM",
        },
        "repeated_cycle":  {
            "title":   "Repeated Circular Flow",
            "detail":  "The same circular-flow pattern involving this account "
                       "appears multiple times, indicating deliberate repetition.",
            "weight":  "HIGH",
        },
    }

    for p in patterns:
        if p in explanations:
            flags.append({"pattern": p, **explanations[p]})

    # Network-based signals
    if stats.get("degree_total", 0) > 10:
        flags.append({
            "pattern": "high_connectivity",
            "title":   "High Network Connectivity",
            "detail":  f"Connected to {stats['degree_total']} other accounts — "
                       "far above average for this dataset.",
            "weight":  "MEDIUM",
        })

    # ML signal (when no specific patterns explain it)
    if score >= 70 and not patterns:
        flags.append({
            "pattern": "ml_anomaly",
            "title":   "ML Anomaly Detected",
            "detail":  "IsolationForest identified this account's transaction "
                       "behaviour as a statistical outlier with no clear rule match.",
            "weight":  "HIGH",
        })

    return {
        "risk_score":   round(score, 2),
        "risk_band":    _band(score),
        "flag_count":   len(flags),
        "flags":        flags,
        "summary":      (
            f"Account has {len(flags)} risk signal(s). "
            + ("Immediate review recommended." if score >= 70 else
               "Monitor closely." if score >= 40 else "No immediate action needed.")
        ),
    }


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get(
    "/account/{account_id}",
    summary="Full fraud profile for a single account",
)
def get_account(
    account_id: str,
    tx_limit: int = Query(50, description="Max transactions to return"),
):
    """
    Returns a complete fraud profile including:

    - **risk_score** and **risk_band**
    - **explanation** — structured, UI-ready explainability object
    - **transactions** — sent + received (sorted newest first)
    - **neighbours**  — direct peers with their risk scores
    - **stats**       — totals, degree, channels used
    """
    g = graph_builder.get_graph()
    if g is None or account_id not in g.nodes:
        raise HTTPException(
            status_code=404,
            detail=f"Account '{account_id}' not found. Run /ingest first.",
        )

    node_data   = g.nodes[account_id]
    risk_scores = scorer.get_all_scores()
    score       = risk_scores.get(account_id, 0.0)
    patterns    = node_data.get("patterns", [])

    # ── Transactions ──────────────────────────────────────────────────────
    sent_edges     = list(g.out_edges(account_id, data=True))
    received_edges = list(g.in_edges(account_id, data=True))

    sent = [
        {
            "direction":    "sent",
            "counterparty": v,
            "amount":       float(d.get("amount", 0)),
            "timestamp":    str(d.get("timestamp", "")),
            "channel":      d.get("channel", "unknown"),
            "tx_id":        d.get("txId", ""),
        }
        for _, v, d in sent_edges
    ]
    received = [
        {
            "direction":    "received",
            "counterparty": u,
            "amount":       float(d.get("amount", 0)),
            "timestamp":    str(d.get("timestamp", "")),
            "channel":      d.get("channel", "unknown"),
            "tx_id":        d.get("txId", ""),
        }
        for u, _, d in received_edges
    ]

    all_tx = sorted(sent + received, key=lambda x: x["timestamp"], reverse=True)[:tx_limit]

    # ── Neighbours ────────────────────────────────────────────────────────
    neighbour_ids: dict = {}
    for _, v, _ in sent_edges:
        neighbour_ids[v] = risk_scores.get(v, 0.0)
    for u, _, _ in received_edges:
        neighbour_ids[u] = risk_scores.get(u, 0.0)

    # ── Aggregate stats ───────────────────────────────────────────────────
    total_sent     = sum(d.get("amount", 0) for _, _, d in sent_edges)
    total_received = sum(d.get("amount", 0) for _, _, d in received_edges)
    channels       = list({d.get("channel", "unknown") for _, _, d in sent_edges + received_edges})

    stats = {
        "total_sent":            round(total_sent, 2),
        "total_received":        round(total_received, 2),
        "net_flow":              round(total_received - total_sent, 2),
        "tx_count_sent":         len(sent_edges),
        "tx_count_received":     len(received_edges),
        "unique_counterparties": len(neighbour_ids),
        "degree_total":          g.degree(account_id),
        "degree_in":             g.in_degree(account_id),
        "degree_out":            g.out_degree(account_id),
        "channels_used":         channels,
    }

    return {
        "account_id":    account_id,
        "risk_score":    round(score, 2),
        "risk_band":     _band(score),
        "flagged":       score >= 70,
        "anomaly_score": node_data.get("anomaly_score"),
        "patterns":      patterns,
        "explanation":   _build_explanation(patterns, score, stats),
        "stats":         stats,
        "transactions":  all_tx,
        "neighbours": sorted(
            [
                {
                    "account_id": nid,
                    "risk_score": round(ns, 2),
                    "risk_band":  _band(ns),
                    "flagged":    ns >= 70,
                }
                for nid, ns in neighbour_ids.items()
            ],
            key=lambda x: -x["risk_score"],
        ),
    }


@router.get("/accounts", summary="List all accounts (lightweight)")
def list_accounts(
    limit:        int  = Query(200,  description="Max records"),
    flagged_only: bool = Query(False, description="Only HIGH-risk accounts"),
):
    """Quick listing for populating tables or dropdowns in the UI."""
    g = graph_builder.get_graph()
    if g is None or g.number_of_nodes() == 0:
        return {"accounts": [], "message": "Run /ingest first."}

    risk_scores = scorer.get_all_scores()
    accounts = [
        {
            "account_id": n,
            "risk_score": round(risk_scores.get(n, 0), 2),
            "risk_band":  _band(risk_scores.get(n, 0)),
            "flagged":    risk_scores.get(n, 0) >= 70,
            "degree":     g.degree(n),
            "patterns":   g.nodes[n].get("patterns", []),
        }
        for n in g.nodes
    ]
    if flagged_only:
        accounts = [a for a in accounts if a["flagged"]]

    accounts.sort(key=lambda x: -x["risk_score"])
    return {"total": len(accounts), "accounts": accounts[:limit]}