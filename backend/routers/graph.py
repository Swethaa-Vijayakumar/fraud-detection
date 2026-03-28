"""
routers/graph.py
================
Returns the transaction network graph as JSON ready for vis-network / D3.

Endpoints
---------
GET /api/v1/graph        — nodes + edges (≤ 100 edges by default)
GET /api/v1/graph/stats  — aggregate statistics
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from services.graph_builder import graph_builder
from services.neo4j_service import neo4j_service
from services.scorer import scorer

logger = logging.getLogger("fraudlink.graph")
router = APIRouter()

# Hard cap: never send more edges than this to the frontend
MAX_EDGES = 100


# ── Colour / type helpers ──────────────────────────────────────────────────

def _node_color(score: float) -> str:
    """Map a risk score to a hex colour for vis-network / D3."""
    if score >= 70:
        return "#ff2d55"   # red   — high risk
    if score >= 40:
        return "#ffbb00"   # amber — medium risk
    return "#00ff88"       # green — low risk


def _node_type(score: float) -> str:
    if score >= 70:
        return "high_risk"
    if score >= 40:
        return "medium_risk"
    return "low_risk"


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get(
    "/graph",
    summary="Get transaction graph (nodes + edges)",
    response_description="nodes[] and edges[] for graph visualisation",
)
def get_graph(
    min_risk:  float = Query(0.0,   description="Minimum risk score to include (0–100)"),
    max_edges: int   = Query(MAX_EDGES, description="Cap on edges returned (max 100)"),
    channel:   str   = Query(None,  description="Filter by payment channel"),
):
    """
    Returns the fraud transaction network.

    Response is directly compatible with **vis-network** `{nodes, edges}`.

    - `nodes` — accounts with id, label, riskScore, color, type, patterns
    - `edges` — transfers with source, target, amount, channel, suspicious flag

    Output is capped at `max_edges` (default 100) for browser performance.
    """
    try:
        max_edges = min(max_edges, MAX_EDGES)   # enforce hard cap

        if neo4j_service.is_connected():
            return _from_neo4j(min_risk, max_edges, channel)
        return _from_memory(min_risk, max_edges, channel)

    except Exception as exc:
        logger.exception("Graph endpoint failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/graph/stats", summary="Aggregate graph statistics")
def graph_stats():
    """Returns node/edge counts and risk-band distribution."""
    g = graph_builder.get_graph()
    if g is None or g.number_of_nodes() == 0:
        return {"message": "No graph loaded — POST to /ingest first."}

    risk_scores = scorer.get_all_scores()
    values      = list(risk_scores.values())

    return {
        "total_accounts": g.number_of_nodes(),
        "total_edges":    g.number_of_edges(),
        "risk_bands": {
            "high":   sum(1 for s in values if s >= 70),
            "medium": sum(1 for s in values if 40 <= s < 70),
            "low":    sum(1 for s in values if s < 40),
        },
        "mean_score": round(sum(values) / len(values), 2) if values else 0,
        "max_score":  round(max(values), 2) if values else 0,
    }


# ── Private: Neo4j ─────────────────────────────────────────────────────────

def _from_neo4j(min_risk: float, max_edges: int, channel):
    """Build graph response from a live Neo4j query."""
    ch_filter = "AND t.channel = $channel" if channel else ""

    nodes_raw = neo4j_service.run(
        """
        MATCH (a:Account)
        WHERE a.riskScore >= $min_risk
        RETURN a.id        AS id,
               a.riskScore AS riskScore,
               a.flagged   AS flagged,
               a.patterns  AS patterns
        ORDER BY a.riskScore DESC
        LIMIT 500
        """,
        min_risk=min_risk,
    )

    edges_raw = neo4j_service.run(
        f"""
        MATCH (s:Account)-[t:TRANSFER]->(r:Account)
        WHERE s.riskScore >= $min_risk OR r.riskScore >= $min_risk
        {ch_filter}
        RETURN s.id        AS source,
               r.id        AS target,
               t.amount    AS amount,
               t.timestamp AS timestamp,
               t.channel   AS channel,
               t.txId      AS txId
        LIMIT $limit
        """,
        min_risk=min_risk,
        channel=channel or "",
        limit=max_edges,
    )

    high_ids = {r["id"] for r in nodes_raw if (r.get("riskScore") or 0) >= 70}

    nodes = [
        {
            "id":        r["id"],
            "label":     r["id"],
            "riskScore": round(r.get("riskScore") or 0, 1),
            "color":     _node_color(r.get("riskScore") or 0),
            "type":      _node_type(r.get("riskScore") or 0),
            "flagged":   bool(r.get("flagged")),
            "patterns":  r.get("patterns") or [],
        }
        for r in nodes_raw
    ]
    edges = [
        {
            "id":         r.get("txId") or f"{r['source']}->{r['target']}",
            "source":     r["source"],
            "target":     r["target"],
            "amount":     float(r.get("amount") or 0),
            "timestamp":  str(r.get("timestamp") or ""),
            "channel":    r.get("channel") or "unknown",
            "suspicious": r["source"] in high_ids or r["target"] in high_ids,
        }
        for r in edges_raw
    ]
    return {"nodes": nodes, "edges": edges, "source": "neo4j",
            "edge_count": len(edges), "node_count": len(nodes)}


# ── Private: in-memory NetworkX ────────────────────────────────────────────

def _from_memory(min_risk: float, max_edges: int, channel):
    """Fall back to the in-memory NetworkX graph when Neo4j is not available."""
    g = graph_builder.get_graph()
    if g is None or g.number_of_nodes() == 0:
        return {"nodes": [], "edges": [], "source": "none",
                "message": "No graph — POST to /ingest first."}

    risk_scores  = scorer.get_all_scores()

    # Sort nodes by risk score, apply min_risk filter
    all_nodes = sorted(
        g.nodes(data=True),
        key=lambda x: risk_scores.get(x[0], 0),
        reverse=True,
    )
    filtered_nodes = [(n, d) for n, d in all_nodes if risk_scores.get(n, 0) >= min_risk]
    node_set       = {n for n, _ in filtered_nodes}
    high_ids       = {n for n in node_set if risk_scores.get(n, 0) >= 70}

    nodes = [
        {
            "id":        n,
            "label":     n,
            "riskScore": round(risk_scores.get(n, 0), 1),
            "color":     _node_color(risk_scores.get(n, 0)),
            "type":      _node_type(risk_scores.get(n, 0)),
            "flagged":   risk_scores.get(n, 0) >= 70,
            "patterns":  d.get("patterns", []),
        }
        for n, d in filtered_nodes
    ]

    # Collect edges (cap at max_edges)
    edges = []
    for u, v, data in g.edges(data=True):
        if len(edges) >= max_edges:
            break
        if u not in node_set and v not in node_set:
            continue
        if channel and data.get("channel") != channel:
            continue
        edges.append({
            "id":         data.get("txId") or f"{u}->{v}",
            "source":     u,
            "target":     v,
            "amount":     float(data.get("amount", 0)),
            "timestamp":  str(data.get("timestamp", "")),
            "channel":    data.get("channel", "unknown"),
            "suspicious": u in high_ids or v in high_ids,
        })

    return {"nodes": nodes, "edges": edges, "source": "memory",
            "edge_count": len(edges), "node_count": len(nodes),
            "edges_capped": g.number_of_edges() > max_edges}