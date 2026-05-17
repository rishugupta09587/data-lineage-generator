"""
routes/dag_routes.py
---------------------
All API route handlers for the Data Lineage Generator.

Endpoints:
  POST /upload-dag         - Upload and store a new DAG
  GET  /dags               - List all stored DAGs
  GET  /dags/{dag_id}      - Get DAG details + stats
  DELETE /dags/{dag_id}    - Delete a DAG
  GET  /upstream/{dag_id}/{node_id}
  GET  /downstream/{dag_id}/{node_id}
  GET  /full-lineage/{dag_id}/{node_id}
  GET  /impact-analysis/{dag_id}/{node_id}
  GET  /column-lineage/{dag_id}/{node_id}/{column}
  GET  /export/{dag_id}/{node_id} - Export lineage (PDF/JSON)
  GET  /graph-stats/{dag_id}  - Graph statistics
"""

import uuid
import json
import logging
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse, JSONResponse
import io

from sqlalchemy.orm import Session
from database import get_db
from models.db_models import DAGRecord, NodeRecord, EdgeRecord
from models.schemas import (
    DAGInput, DAGResponse, DAGListResponse, DAGSummary,
    LineageResponse, ImpactAnalysisResponse
)
from services import lineage_service
from utils.validators import validate_dag
from utils.export_utils import export_to_json, export_to_pdf

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── DAG Upload ───────────────────────────────────────────────────────────

@router.post(
    "/upload-dag",
    response_model=DAGResponse,
    summary="Upload a new Data Pipeline DAG",
    tags=["DAG Management"],
)
def upload_dag(dag_input: DAGInput, db: Session = Depends(get_db)):
    """
    Upload a DAG representing a data pipeline.

    - Validates DAG structure (checks for cycles, orphan nodes)
    - Stores nodes, edges, and metadata in the database
    - Returns a dag_id for subsequent lineage queries
    """
    # ── Validate DAG structure ───────────────────────────────────────
    is_valid, error_msg, cycle_path = validate_dag(dag_input)
    if not is_valid:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Invalid DAG structure",
                "message": error_msg,
                "cycle_path": cycle_path,
            }
        )

    dag_id = str(uuid.uuid4())

    # ── Store DAG record ─────────────────────────────────────────────
    dag_record = DAGRecord(
        id=dag_id,
        name=dag_input.name,
        description=dag_input.description,
        version=dag_input.version,
        raw_json=dag_input.model_dump(mode="json"),
    )
    db.add(dag_record)

    # ── Store nodes ──────────────────────────────────────────────────
    for node in dag_input.nodes:
        db.add(NodeRecord(
            id=str(uuid.uuid4()),
            dag_id=dag_id,
            node_id=node.id,
            name=node.name or node.id,
            type=node.type.value,
            operation=node.operation,
            description=node.description,
            schema_info=node.schema_info,
            tags=node.tags,
            version=node.version,
        ))

    # ── Store edges ──────────────────────────────────────────────────
    for edge in dag_input.edges:
        db.add(EdgeRecord(
            id=str(uuid.uuid4()),
            dag_id=dag_id,
            from_node=edge.from_,
            to_node=edge.to,
            relationship_type=edge.relationship_type,
            column_mapping=edge.column_mapping,
        ))

    db.commit()
    logger.info("DAG uploaded: %s (%s nodes, %s edges)",
                dag_id, len(dag_input.nodes), len(dag_input.edges))

    return DAGResponse(
        dag_id=dag_id,
        name=dag_input.name,
        version=dag_input.version,
        node_count=len(dag_input.nodes),
        edge_count=len(dag_input.edges),
        created_at=datetime.utcnow(),
    )


@router.post(
    "/upload-dag/file",
    response_model=DAGResponse,
    summary="Upload a DAG from a JSON file",
    tags=["DAG Management"],
)
async def upload_dag_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a DAG definition from a .json file.
    File must follow the DAGInput schema.
    """
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files are supported")

    try:
        content = await file.read()
        data = json.loads(content)
        dag_input = DAGInput(**data)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid DAG structure: {str(e)}")

    # Reuse the main upload logic
    return upload_dag(dag_input, db)


# ─── DAG Management ───────────────────────────────────────────────────────

@router.get(
    "/dags",
    response_model=DAGListResponse,
    summary="List all stored DAGs",
    tags=["DAG Management"],
)
def list_dags(db: Session = Depends(get_db)):
    """Return a summary list of all uploaded DAGs."""
    records = db.query(DAGRecord).order_by(DAGRecord.created_at.desc()).all()
    summaries = []
    for r in records:
        node_count = db.query(NodeRecord).filter(NodeRecord.dag_id == r.id).count()
        edge_count = db.query(EdgeRecord).filter(EdgeRecord.dag_id == r.id).count()
        summaries.append(DAGSummary(
            dag_id=r.id,
            name=r.name,
            version=r.version,
            node_count=node_count,
            edge_count=edge_count,
            created_at=r.created_at,
        ))
    return DAGListResponse(dags=summaries, total=len(summaries))


@router.get(
    "/dags/{dag_id}",
    summary="Get DAG details and statistics",
    tags=["DAG Management"],
)
def get_dag(dag_id: str, db: Session = Depends(get_db)):
    """Return full DAG info including node list, edge list, and graph statistics."""
    dag = db.query(DAGRecord).filter(DAGRecord.id == dag_id).first()
    if not dag:
        raise HTTPException(status_code=404, detail=f"DAG '{dag_id}' not found")

    nodes = db.query(NodeRecord).filter(NodeRecord.dag_id == dag_id).all()
    edges = db.query(EdgeRecord).filter(EdgeRecord.dag_id == dag_id).all()

    # Graph statistics
    try:
        stats = lineage_service.get_graph_stats(dag_id, db)
    except Exception as e:
        stats = {"error": str(e)}

    return {
        "dag_id": dag_id,
        "name": dag.name,
        "description": dag.description,
        "version": dag.version,
        "created_at": dag.created_at,
        "nodes": [
            {
                "id": n.node_id,
                "name": n.name,
                "type": n.type,
                "operation": n.operation,
                "description": n.description,
                "schema_info": n.schema_info,
                "tags": n.tags,
                "version": n.version,
            }
            for n in nodes
        ],
        "edges": [
            {
                "from": e.from_node,
                "to": e.to_node,
                "relationship_type": e.relationship_type,
                "column_mapping": e.column_mapping,
            }
            for e in edges
        ],
        "stats": stats,
    }


@router.delete(
    "/dags/{dag_id}",
    summary="Delete a DAG",
    tags=["DAG Management"],
)
def delete_dag(dag_id: str, db: Session = Depends(get_db)):
    """Delete a DAG and all its associated nodes, edges, and cached lineage."""
    dag = db.query(DAGRecord).filter(DAGRecord.id == dag_id).first()
    if not dag:
        raise HTTPException(status_code=404, detail=f"DAG '{dag_id}' not found")

    lineage_service.invalidate_cache(dag_id, db)
    db.delete(dag)
    db.commit()
    return {"message": f"DAG '{dag_id}' deleted successfully"}


# ─── Lineage Endpoints ────────────────────────────────────────────────────

@router.get(
    "/upstream/{dag_id}/{node_id}",
    response_model=LineageResponse,
    summary="Get upstream lineage for a node",
    tags=["Lineage Analysis"],
)
def upstream_lineage(dag_id: str, node_id: str, db: Session = Depends(get_db)):
    """
    Returns all ancestor nodes and edges for the given node.
    Upstream = all nodes that directly or indirectly produce data consumed by this node.
    """
    try:
        return lineage_service.get_upstream_lineage(dag_id, node_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/downstream/{dag_id}/{node_id}",
    response_model=LineageResponse,
    summary="Get downstream lineage for a node",
    tags=["Lineage Analysis"],
)
def downstream_lineage(dag_id: str, node_id: str, db: Session = Depends(get_db)):
    """
    Returns all descendant nodes and edges for the given node.
    Downstream = all nodes that consume data produced by this node.
    """
    try:
        return lineage_service.get_downstream_lineage(dag_id, node_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/full-lineage/{dag_id}/{node_id}",
    response_model=LineageResponse,
    summary="Get full lineage (upstream + downstream) for a node",
    tags=["Lineage Analysis"],
)
def full_lineage(dag_id: str, node_id: str, db: Session = Depends(get_db)):
    """
    Returns the complete lineage subgraph: all ancestors and all descendants.
    Provides the full context of a node in the pipeline.
    """
    try:
        return lineage_service.get_full_lineage(dag_id, node_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/impact-analysis/{dag_id}/{node_id}",
    response_model=ImpactAnalysisResponse,
    summary="Impact analysis: what breaks if this node fails?",
    tags=["Impact Analysis"],
)
def impact_analysis(dag_id: str, node_id: str, db: Session = Depends(get_db)):
    """
    Analyzes the downstream impact of a node failure.
    Returns affected nodes, impact score (0-1), and risk level (LOW/MEDIUM/HIGH/CRITICAL).
    """
    try:
        return lineage_service.get_impact_analysis(dag_id, node_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/graph-stats/{dag_id}",
    summary="Get graph-level statistics for a DAG",
    tags=["DAG Management"],
)
def graph_stats(dag_id: str, db: Session = Depends(get_db)):
    """Returns node count, edge count, sources, sinks, critical path, and density."""
    try:
        return lineage_service.get_graph_stats(dag_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─── Export Endpoints ─────────────────────────────────────────────────────

@router.get(
    "/export/{dag_id}/{node_id}",
    summary="Export lineage report as PDF or JSON",
    tags=["Export"],
)
def export_lineage(
    dag_id: str,
    node_id: str,
    format: str = Query("json", enum=["json", "pdf"]),
    lineage_type: str = Query("full", enum=["upstream", "downstream", "full", "impact"]),
    db: Session = Depends(get_db),
):
    """
    Export lineage report for a node.
    - format=json → downloadable JSON file
    - format=pdf  → downloadable PDF report
    """
    try:
        # Compute the appropriate lineage type
        if lineage_type == "upstream":
            result = lineage_service.get_upstream_lineage(dag_id, node_id, db)
        elif lineage_type == "downstream":
            result = lineage_service.get_downstream_lineage(dag_id, node_id, db)
        elif lineage_type == "impact":
            result = lineage_service.get_impact_analysis(dag_id, node_id, db)
        else:
            result = lineage_service.get_full_lineage(dag_id, node_id, db)

        data = result.model_dump(mode="json")

        if format == "pdf":
            pdf_bytes = export_to_pdf(data)
            filename = f"lineage_{node_id}_{lineage_type}.pdf"
            return StreamingResponse(
                io.BytesIO(pdf_bytes),
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )
        else:
            json_bytes = export_to_json(data)
            filename = f"lineage_{node_id}_{lineage_type}.json"
            return StreamingResponse(
                io.BytesIO(json_bytes),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
