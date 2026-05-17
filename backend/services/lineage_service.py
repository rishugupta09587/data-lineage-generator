"""
services/lineage_service.py
----------------------------
Orchestrates lineage operations:
  1. Load graph from database
  2. Run graph traversal via GraphTraversalService
  3. Enrich results with node metadata
  4. Cache results for performance
  5. Return structured LineageResponse objects

This layer bridges the route handlers (HTTP) and the graph engine (algorithms).
"""

import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from models.db_models import NodeRecord, EdgeRecord, LineageCacheRecord, DAGRecord
from models.schemas import (
    NodeResponse, EdgeResponse, LineageResponse, LineagePath,
    ImpactAnalysisResponse
)
from services.graph_service import GraphTraversalService
from utils.validators import build_networkx_graph

logger = logging.getLogger(__name__)


def _load_graph(dag_id: str, db: Session) -> GraphTraversalService:
    """
    Load a DAG from the database and build a NetworkX graph.
    Raises ValueError if dag_id not found.
    """
    nodes = db.query(NodeRecord).filter(NodeRecord.dag_id == dag_id).all()
    edges = db.query(EdgeRecord).filter(EdgeRecord.dag_id == dag_id).all()

    if not nodes:
        raise ValueError(f"DAG '{dag_id}' not found or has no nodes")

    G = build_networkx_graph(nodes, edges)
    return GraphTraversalService(G)


def _nodes_to_response(
    node_ids: set,
    dag_id: str,
    db: Session
) -> List[NodeResponse]:
    """Fetch node metadata from DB and convert to response objects."""
    records = (
        db.query(NodeRecord)
        .filter(NodeRecord.dag_id == dag_id, NodeRecord.node_id.in_(node_ids))
        .all()
    )
    return [
        NodeResponse(
            id=r.node_id,
            name=r.name,
            type=r.type,
            operation=r.operation,
            description=r.description,
            schema_info=r.schema_info,
            tags=r.tags,
            version=r.version,
            created_at=r.created_at,
        )
        for r in records
    ]


def _edges_to_response(
    edges: List[tuple],
    dag_id: str,
    db: Session
) -> List[EdgeResponse]:
    """Convert (from, to) edge tuples to response objects with metadata."""
    # Build a lookup dict from DB for edge metadata
    db_edges = db.query(EdgeRecord).filter(EdgeRecord.dag_id == dag_id).all()
    edge_meta = {(e.from_node, e.to_node): e for e in db_edges}

    result = []
    for from_node, to_node in edges:
        meta = edge_meta.get((from_node, to_node))
        result.append(EdgeResponse(
            from_node=from_node,
            to_node=to_node,
            relationship_type=meta.relationship_type if meta else None,
            column_mapping=meta.column_mapping if meta else None,
        ))
    return result


def _check_cache(
    dag_id: str, node_id: str, lineage_type: str, db: Session
) -> Optional[Dict[str, Any]]:
    """Return cached lineage result if available, else None."""
    record = (
        db.query(LineageCacheRecord)
        .filter(
            LineageCacheRecord.dag_id == dag_id,
            LineageCacheRecord.node_id == node_id,
            LineageCacheRecord.lineage_type == lineage_type,
        )
        .first()
    )
    if record:
        logger.debug("Cache hit: %s/%s/%s", dag_id, node_id, lineage_type)
        return record.result_json
    return None


def _store_cache(
    dag_id: str, node_id: str, lineage_type: str,
    result: Dict[str, Any], db: Session
):
    """Upsert a lineage result into the cache table."""
    existing = (
        db.query(LineageCacheRecord)
        .filter(
            LineageCacheRecord.dag_id == dag_id,
            LineageCacheRecord.node_id == node_id,
            LineageCacheRecord.lineage_type == lineage_type,
        )
        .first()
    )
    if existing:
        existing.result_json = result
        existing.computed_at = datetime.utcnow()
    else:
        db.add(LineageCacheRecord(
            id=str(uuid.uuid4()),
            dag_id=dag_id,
            node_id=node_id,
            lineage_type=lineage_type,
            result_json=result,
        ))
    db.commit()


def get_upstream_lineage(dag_id: str, node_id: str, db: Session) -> LineageResponse:
    """
    Compute upstream lineage for node_id in dag_id.
    Returns all ancestor nodes and edges with path information.
    """
    # ── Cache check ─────────────────────────────────────────────────
    cached = _check_cache(dag_id, node_id, "upstream", db)
    if cached:
        response = LineageResponse(**cached)
        response.from_cache = True
        return response

    # ── Graph traversal ──────────────────────────────────────────────
    service = _load_graph(dag_id, db)
    ancestors, edges = service.get_upstream(node_id)
    paths_raw = service.find_all_paths_to(node_id)

    # ── Build response ───────────────────────────────────────────────
    all_node_ids = ancestors | {node_id}
    nodes_response = _nodes_to_response(all_node_ids, dag_id, db)
    edges_response = _edges_to_response(edges, dag_id, db)
    paths = [
        LineagePath(path=p, length=len(p) - 1)
        for p in paths_raw
    ]
    depth = max((len(p) - 1 for p in paths_raw), default=0)

    response = LineageResponse(
        query_node=node_id,
        lineage_type="upstream",
        nodes=nodes_response,
        edges=edges_response,
        paths=paths,
        depth=depth,
        node_count=len(nodes_response),
        from_cache=False,
    )

    # ── Cache result ─────────────────────────────────────────────────
    _store_cache(dag_id, node_id, "upstream", response.model_dump(mode="json"), db)
    return response


def get_downstream_lineage(dag_id: str, node_id: str, db: Session) -> LineageResponse:
    """
    Compute downstream lineage for node_id.
    Returns all descendant nodes and edges.
    """
    cached = _check_cache(dag_id, node_id, "downstream", db)
    if cached:
        response = LineageResponse(**cached)
        response.from_cache = True
        return response

    service = _load_graph(dag_id, db)
    descendants, edges = service.get_downstream(node_id)
    paths_raw = service.find_all_paths_from(node_id)

    all_node_ids = descendants | {node_id}
    nodes_response = _nodes_to_response(all_node_ids, dag_id, db)
    edges_response = _edges_to_response(edges, dag_id, db)
    paths = [LineagePath(path=p, length=len(p) - 1) for p in paths_raw]
    depth = max((len(p) - 1 for p in paths_raw), default=0)

    response = LineageResponse(
        query_node=node_id,
        lineage_type="downstream",
        nodes=nodes_response,
        edges=edges_response,
        paths=paths,
        depth=depth,
        node_count=len(nodes_response),
        from_cache=False,
    )
    _store_cache(dag_id, node_id, "downstream", response.model_dump(mode="json"), db)
    return response


def get_full_lineage(dag_id: str, node_id: str, db: Session) -> LineageResponse:
    """
    Compute full lineage: ancestors + node + descendants.
    Combines upstream and downstream path traces.
    """
    cached = _check_cache(dag_id, node_id, "full", db)
    if cached:
        response = LineageResponse(**cached)
        response.from_cache = True
        return response

    service = _load_graph(dag_id, db)
    all_nodes, edges = service.get_full_lineage(node_id)
    upstream_paths = service.find_all_paths_to(node_id)
    downstream_paths = service.find_all_paths_from(node_id)
    all_paths_raw = upstream_paths + downstream_paths

    nodes_response = _nodes_to_response(all_nodes, dag_id, db)
    edges_response = _edges_to_response(edges, dag_id, db)
    paths = [LineagePath(path=p, length=len(p) - 1) for p in all_paths_raw]
    depth = max((len(p) - 1 for p in all_paths_raw), default=0)

    response = LineageResponse(
        query_node=node_id,
        lineage_type="full",
        nodes=nodes_response,
        edges=edges_response,
        paths=paths,
        depth=depth,
        node_count=len(nodes_response),
        from_cache=False,
    )
    _store_cache(dag_id, node_id, "full", response.model_dump(mode="json"), db)
    return response


def get_impact_analysis(dag_id: str, node_id: str, db: Session) -> ImpactAnalysisResponse:
    """
    Compute impact analysis: what breaks if node_id fails?
    """
    cached = _check_cache(dag_id, node_id, "impact", db)
    if cached:
        return ImpactAnalysisResponse(**cached)

    service = _load_graph(dag_id, db)
    impact = service.compute_impact(node_id)

    all_node_ids = set(impact["transitively_affected"]) | {node_id}
    nodes_response = _nodes_to_response(all_node_ids, dag_id, db)
    edges_response = _edges_to_response(impact["affected_edges"], dag_id, db)

    response = ImpactAnalysisResponse(
        failed_node=node_id,
        directly_affected=impact["directly_affected"],
        transitively_affected=impact["transitively_affected"],
        nodes=nodes_response,
        edges=edges_response,
        impact_score=impact["impact_score"],
        risk_level=impact["risk_level"],
    )
    _store_cache(dag_id, node_id, "impact", response.model_dump(mode="json"), db)
    return response


def get_graph_stats(dag_id: str, db: Session) -> Dict[str, Any]:
    """Return graph-level statistics for a DAG."""
    service = _load_graph(dag_id, db)
    return service.get_graph_stats()


def invalidate_cache(dag_id: str, db: Session):
    """
    Invalidate all cached lineage results for a DAG.
    Called when the DAG is updated/re-uploaded.
    """
    db.query(LineageCacheRecord).filter(
        LineageCacheRecord.dag_id == dag_id
    ).delete()
    db.commit()
    logger.info("Cache invalidated for DAG: %s", dag_id)
