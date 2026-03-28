"""
routers/ingest.py
=================
Handles CSV ingestion and triggers the full fraud-detection pipeline.

Endpoints
---------
POST /api/v1/ingest         — upload a CSV file
POST /api/v1/ingest/sample  — run the pipeline on bundled sample data
"""

import io
import logging
from typing import Optional

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ml.classifier import anomaly_classifier
from ml.feature_extractor import feature_extractor
from services.fraud_detector import fraud_detector
from services.graph_builder import graph_builder
from services.scorer import scorer

logger = logging.getLogger("fraudlink.ingest")
router = APIRouter()

# Columns every CSV must contain
REQUIRED_COLUMNS = {"sender", "receiver", "amount", "timestamp"}


# ── Helpers ────────────────────────────────────────────────────────────────

def _validate_and_clean(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise column names, coerce types, and drop unusable rows.

    Raises
    ------
    HTTPException 422 if required columns are missing.
    """
    df.columns = [c.strip().lower() for c in df.columns]

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"CSV is missing required columns: {sorted(missing)}",
        )

    df["amount"]    = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["sender", "receiver", "timestamp"])
    df["sender"]   = df["sender"].astype(str).str.strip()
    df["receiver"] = df["receiver"].astype(str).str.strip()

    # Remove self-loops (account sending to itself)
    df = df[df["sender"] != df["receiver"]]
    return df.reset_index(drop=True)


def _run_full_pipeline(df: pd.DataFrame) -> dict:
    """
    Execute the end-to-end fraud detection pipeline:

    1. Build graph (NetworkX + Neo4j)
    2. Run rule-based fraud detectors
    3. Extract ML features via NetworkX
    4. Fit IsolationForest and generate anomaly scores
    5. Compute composite risk scores
    6. Persist scores back to graph nodes

    Returns a summary dict suitable for the API response.
    """
    logger.info("Pipeline start — %d transactions", len(df))

    # Step 1 — Graph
    nx_graph = graph_builder.build(df)

    # Step 2 — Rule-based patterns
    patterns = fraud_detector.detect_all(nx_graph, df)

    # Step 3 & 4 — ML
    feature_df     = feature_extractor.extract(nx_graph, df)
    anomaly_scores = anomaly_classifier.fit_predict(feature_df)

    # Step 5 — Composite risk scoring
    risk_scores = scorer.compute(patterns, anomaly_scores, nx_graph, df)

    # Step 6 — Write scores back to nodes / Neo4j
    graph_builder.persist_scores(risk_scores)

    high_risk = sum(1 for s in risk_scores.values() if s >= 70)
    return {
        "transactions_loaded": len(df),
        "unique_accounts":     nx_graph.number_of_nodes(),
        "graph_edges":         nx_graph.number_of_edges(),
        "patterns_detected":   {k: len(v) for k, v in patterns.items()},
        "high_risk_accounts":  high_risk,
        "sample_scores":       dict(list(risk_scores.items())[:5]),
    }


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post(
    "/ingest",
    summary="Upload transaction CSV and run fraud detection pipeline",
)
async def ingest_csv(
    file: Optional[UploadFile] = File(
        None,
        description=(
            "CSV file with columns: sender, receiver, amount, timestamp. "
            "Leave empty to run on the bundled sample data."
        ),
    ),
):
    """
    Accepts a transaction CSV, validates it, builds the fraud graph,
    runs ML detection and returns a pipeline summary.

    If **no file is attached** the bundled `sample_transactions.csv`
    is used automatically — useful for demos.
    """
    try:
        if file is not None:
            raw = await file.read()
            df  = pd.read_csv(io.BytesIO(raw))
            logger.info("Received upload: %s (%d bytes)", file.filename, len(raw))
        else:
            df = pd.read_csv("data/sample_transactions.csv")
            logger.info("No file — using sample_transactions.csv")

        df      = _validate_and_clean(df)
        summary = _run_full_pipeline(df)
        return JSONResponse({"status": "success", "summary": summary})

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Pipeline failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/ingest/sample", summary="Run pipeline on bundled sample data")
def ingest_sample():
    """Shortcut that always uses the bundled sample CSV (no upload needed)."""
    try:
        df      = pd.read_csv("data/sample_transactions.csv")
        df      = _validate_and_clean(df)
        summary = _run_full_pipeline(df)
        return {"status": "success", "summary": summary}
    except Exception as exc:
        logger.exception("Sample ingest failed")
        raise HTTPException(status_code=500, detail=str(exc))