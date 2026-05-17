"""
tests/test_api.py
------------------
Integration tests for the FastAPI routes.
Uses TestClient (synchronous) with an in-memory SQLite database.

Run with:
    cd backend
    pytest tests/test_api.py -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ── Patch the database module BEFORE importing anything else ─────────────
# This ensures the test SQLite engine is used everywhere.
import database as db_module
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_TEST_ENGINE = create_engine(
    "sqlite:///./test_lineage.db",
    connect_args={"check_same_thread": False}
)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_TEST_ENGINE)

db_module.engine = _TEST_ENGINE
db_module.SessionLocal = _TestSession

# Now safe to import app (it will use the patched engine)
import pytest
from fastapi.testclient import TestClient
from main import app
from database import Base, get_db, init_db

# Override the DB dependency to inject test sessions
def override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    """Create all tables on the test engine before tests run."""
    # Must import models so Base knows about all tables
    from models import db_models  # noqa
    Base.metadata.create_all(bind=_TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=_TEST_ENGINE)
    # Clean up test DB file
    if os.path.exists("./test_lineage.db"):
        os.remove("./test_lineage.db")


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ── Sample DAG payload ────────────────────────────────────────────────────

SIMPLE_DAG = {
    "name": "Test Pipeline",
    "description": "Integration test DAG",
    "nodes": [
        {"id": "src",    "type": "source"},
        {"id": "clean",  "type": "transformation", "operation": "filter"},
        {"id": "agg",    "type": "transformation", "operation": "aggregation"},
        {"id": "output", "type": "sink"},
    ],
    "edges": [
        {"from": "src",   "to": "clean"},
        {"from": "clean", "to": "agg"},
        {"from": "agg",   "to": "output"},
    ],
}

CYCLIC_DAG = {
    "name": "Cyclic DAG",
    "nodes": [
        {"id": "A", "type": "source"},
        {"id": "B", "type": "transformation"},
        {"id": "C", "type": "sink"},
    ],
    "edges": [
        {"from": "A", "to": "B"},
        {"from": "B", "to": "C"},
        {"from": "C", "to": "A"},   # creates a cycle
    ],
}


# ── Health Check ──────────────────────────────────────────────────────────

class TestHealth:
    def test_root_endpoint(self, client):
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "running"
        assert "docs" in data

    def test_health_endpoint(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"


# ── DAG Upload Tests ──────────────────────────────────────────────────────

class TestDAGUpload:

    def test_upload_valid_dag(self, client):
        """Uploading a valid DAG returns 200 with dag_id."""
        r = client.post("/api/v1/upload-dag", json=SIMPLE_DAG)
        assert r.status_code == 200
        data = r.json()
        assert "dag_id" in data
        assert data["node_count"] == 4
        assert data["edge_count"] == 3
        assert data["name"] == "Test Pipeline"

    def test_upload_cyclic_dag_rejected(self, client):
        """Uploading a cyclic DAG must return 422."""
        r = client.post("/api/v1/upload-dag", json=CYCLIC_DAG)
        assert r.status_code == 422
        data = r.json()
        assert "Cycle" in data["detail"]["message"]

    def test_upload_minimal_dag(self, client):
        """A single-node DAG with no edges is valid."""
        r = client.post("/api/v1/upload-dag", json={
            "name": "Minimal",
            "nodes": [{"id": "only_node", "type": "source"}],
            "edges": [],
        })
        assert r.status_code == 200
        assert r.json()["node_count"] == 1

    def test_upload_missing_nodes_field(self, client):
        """Uploading DAG without 'nodes' must fail validation."""
        r = client.post("/api/v1/upload-dag", json={"edges": []})
        assert r.status_code == 422


# ── DAG Management Tests ──────────────────────────────────────────────────

class TestDAGManagement:

    @pytest.fixture(scope="class")
    def uploaded_dag_id(self, client):
        """Upload a DAG and return its dag_id for use in tests."""
        r = client.post("/api/v1/upload-dag", json=SIMPLE_DAG)
        return r.json()["dag_id"]

    def test_list_dags(self, client, uploaded_dag_id):
        r = client.get("/api/v1/dags")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        dag_ids = [d["dag_id"] for d in data["dags"]]
        assert uploaded_dag_id in dag_ids

    def test_get_dag_details(self, client, uploaded_dag_id):
        r = client.get(f"/api/v1/dags/{uploaded_dag_id}")
        assert r.status_code == 200
        data = r.json()
        assert len(data["nodes"]) == 4
        assert len(data["edges"]) == 3
        assert "stats" in data

    def test_get_nonexistent_dag_returns_404(self, client):
        r = client.get("/api/v1/dags/nonexistent-dag-id")
        assert r.status_code == 404

    def test_graph_stats(self, client, uploaded_dag_id):
        r = client.get(f"/api/v1/graph-stats/{uploaded_dag_id}")
        assert r.status_code == 200
        stats = r.json()
        assert stats["node_count"] == 4
        assert stats["edge_count"] == 3
        assert stats["source_count"] == 1   # only "src"
        assert stats["sink_count"] == 1     # only "output"


# ── Lineage Analysis Tests ────────────────────────────────────────────────

class TestLineageAnalysis:

    @pytest.fixture(scope="class")
    def dag_id(self, client):
        r = client.post("/api/v1/upload-dag", json=SIMPLE_DAG)
        return r.json()["dag_id"]

    def test_upstream_of_sink(self, client, dag_id):
        r = client.get(f"/api/v1/upstream/{dag_id}/output")
        assert r.status_code == 200
        data = r.json()
        assert data["lineage_type"] == "upstream"
        node_ids = {n["id"] for n in data["nodes"]}
        assert "src" in node_ids
        assert "clean" in node_ids
        assert "agg" in node_ids

    def test_downstream_of_source(self, client, dag_id):
        r = client.get(f"/api/v1/downstream/{dag_id}/src")
        assert r.status_code == 200
        data = r.json()
        node_ids = {n["id"] for n in data["nodes"]}
        assert "clean" in node_ids
        assert "agg" in node_ids
        assert "output" in node_ids

    def test_full_lineage_of_middle_node(self, client, dag_id):
        r = client.get(f"/api/v1/full-lineage/{dag_id}/agg")
        assert r.status_code == 200
        data = r.json()
        node_ids = {n["id"] for n in data["nodes"]}
        assert "src" in node_ids    # upstream
        assert "output" in node_ids  # downstream

    def test_lineage_nonexistent_node_returns_404(self, client, dag_id):
        r = client.get(f"/api/v1/upstream/{dag_id}/ghost_node")
        assert r.status_code == 404

    def test_lineage_caching(self, client, dag_id):
        """Second call to same lineage endpoint should hit cache."""
        url = f"/api/v1/upstream/{dag_id}/output"
        r1 = client.get(url)
        r2 = client.get(url)
        assert r1.status_code == 200
        assert r2.status_code == 200
        # Second call should be from cache
        assert r2.json()["from_cache"] is True


# ── Impact Analysis Tests ─────────────────────────────────────────────────

class TestImpactAnalysis:

    @pytest.fixture(scope="class")
    def dag_id(self, client):
        r = client.post("/api/v1/upload-dag", json=SIMPLE_DAG)
        return r.json()["dag_id"]

    def test_impact_of_source(self, client, dag_id):
        r = client.get(f"/api/v1/impact-analysis/{dag_id}/src")
        assert r.status_code == 200
        data = r.json()
        assert data["failed_node"] == "src"
        assert len(data["transitively_affected"]) == 3  # clean, agg, output
        assert data["risk_level"] in ("HIGH", "CRITICAL")
        assert 0.0 <= data["impact_score"] <= 1.0

    def test_impact_of_sink(self, client, dag_id):
        r = client.get(f"/api/v1/impact-analysis/{dag_id}/output")
        assert r.status_code == 200
        data = r.json()
        assert data["transitively_affected"] == []
        assert data["risk_level"] == "LOW"
        assert data["impact_score"] == 0.0


# ── Delete Tests ─────────────────────────────────────────────────────────

class TestDeleteDAG:

    def test_delete_dag(self, client):
        # Upload a temporary DAG
        r = client.post("/api/v1/upload-dag", json={
            "name": "Temp", "nodes": [{"id": "x", "type": "source"}], "edges": []
        })
        dag_id = r.json()["dag_id"]

        # Delete it
        r = client.delete(f"/api/v1/dags/{dag_id}")
        assert r.status_code == 200

        # Verify it's gone
        r = client.get(f"/api/v1/dags/{dag_id}")
        assert r.status_code == 404

    def test_delete_nonexistent_returns_404(self, client):
        r = client.delete("/api/v1/dags/nonexistent-id")
        assert r.status_code == 404
