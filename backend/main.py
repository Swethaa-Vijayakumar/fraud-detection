"""
FraudLink AI — main.py
======================
FastAPI application entry point.
Registers all routers, configures CORS, and manages the Neo4j
connection lifecycle through FastAPI's lifespan context.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from routers import accounts, graph, ingest, scores
from services.neo4j_service import neo4j_service

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-8s]  %(name)s  →  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("fraudlink.main")


# ── Lifespan (startup / shutdown) ──────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs once on startup (before requests) and once on shutdown.
    Establishes the Neo4j connection and creates schema indexes.
    """
    logger.info("🚀  FraudLink AI starting up …")
    try:
        neo4j_service.connect()
        neo4j_service.create_indexes()
        logger.info("✅  Neo4j connected and schema verified.")
    except Exception as exc:
        logger.warning(
            "⚠️   Neo4j unavailable — running in in-memory mode. Error: %s", exc
        )
    yield
    logger.info("🛑  FraudLink AI shutting down …")
    neo4j_service.close()


# ── App factory ────────────────────────────────────────────────────────────
app = FastAPI(
    title="FraudLink AI",
    description=(
        "## Cross-Channel Mule Account Detection\n\n"
        "Graph-powered fraud detection API combining **Neo4j**, **NetworkX** "
        "and **IsolationForest** to flag suspicious financial accounts.\n\n"
        "### Quick start\n"
        "1. `POST /api/v1/ingest` — upload a transaction CSV\n"
        "2. `GET  /api/v1/graph`  — inspect the transaction network\n"
        "3. `GET  /api/v1/scores` — view ranked risk scores\n"
        "4. `GET  /api/v1/account/{id}` — drill into one account\n"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ── CORS ───────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(ingest.router,   prefix=API_PREFIX, tags=["📥 Ingest"])
app.include_router(graph.router,    prefix=API_PREFIX, tags=["🕸  Graph"])
app.include_router(scores.router,   prefix=API_PREFIX, tags=["📊 Scores"])
app.include_router(accounts.router, prefix=API_PREFIX, tags=["👤 Accounts"])


# ── Health / root ──────────────────────────────────────────────────────────
@app.get("/", tags=["🏥 Health"])
def root():
    """Root endpoint — confirms the API is alive."""
    return {
        "service": "FraudLink AI",
        "version": "1.0.0",
        "docs":    "/docs",
    }


@app.get("/health", tags=["🏥 Health"])
def health():
    """Liveness + readiness probe."""
    return {
        "status":          "ok",
        "neo4j_connected": neo4j_service.is_connected(),
    }

@app.get("/favicon.ico")
def favicon():
    return FileResponse("favicon.ico")