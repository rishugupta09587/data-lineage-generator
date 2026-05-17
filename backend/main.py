"""
main.py
-------
FastAPI application entry point for the Data Lineage Generator.

Features:
  - Auto-generated Swagger UI at /docs
  - CORS enabled for React frontend (localhost:3000 / 5173)
  - Health check endpoint
  - Structured logging
  - Database initialization on startup
"""

import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import init_db
from routes.dag_routes import router as dag_router

# ─── Logging Configuration ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ─── Lifespan (Startup / Shutdown) ─────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs on startup: initialize the database tables.
    Runs on shutdown: cleanup resources (if any).
    """
    logger.info("🚀 Data Lineage Generator starting up...")
    init_db()
    logger.info("✅ Database initialized")
    yield
    logger.info("🛑 Data Lineage Generator shutting down")


# ─── FastAPI App ────────────────────────────────────────────────────────────
app = FastAPI(
    title="Data Lineage Generator API",
    description="""
## Data Lineage Generator from DAG-Based Data Pipelines

A production-grade tool for tracking **data lineage**, **impact analysis**,
and **transformation visibility** in data engineering pipelines.

### Key Features
- **Upload DAGs** in JSON format representing your data pipeline
- **Upstream Lineage**: Trace all data sources feeding into a node
- **Downstream Lineage**: See all nodes consuming data from a node
- **Impact Analysis**: Understand blast radius if a node fails
- **Column-Level Lineage**: Trace individual column transformations
- **Export Reports**: Download lineage as PDF or JSON
- **Caching**: Results cached for high-performance repeated queries

### Designed For
Final-year Computer Science project demonstrating:
- Graph algorithms (BFS/DFS on DAGs)
- REST API design with FastAPI
- Database design (PostgreSQL/SQLite)
- Data engineering concepts (Spark-style DAGs)
    """,
    version="1.0.0",
    contact={
        "name": "Data Lineage Generator",
        "email": "support@datalineage.dev",
    },
    license_info={
        "name": "MIT",
    },
    lifespan=lifespan,
    docs_url="/docs",      # Swagger UI
    redoc_url="/redoc",    # ReDoc UI
)

# ─── CORS Middleware ────────────────────────────────────────────────────────
# Allows the React frontend to communicate with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",    # Create React App
        "http://localhost:5173",    # Vite dev server
        "http://localhost:5174",    # Vite alternate port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ────────────────────────────────────────────────────────────────
app.include_router(dag_router, prefix="/api/v1", tags=["API v1"])


# ─── Health Check ───────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    """API root — returns service info and status."""
    return {
        "service": "Data Lineage Generator",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "api_prefix": "/api/v1",
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint for deployment monitoring."""
    return {"status": "healthy", "timestamp": "now"}


# ─── Global Error Handler ───────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Catch-all exception handler to prevent leaking stack traces."""
    logger.exception("Unhandled exception: %s", str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please check server logs.",
        },
    )


# ─── Entry Point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,       # auto-reload on code changes during development
        log_level="info",
    )
