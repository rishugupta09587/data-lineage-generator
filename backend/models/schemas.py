"""
models/schemas.py
-----------------
Pydantic v2 models for:
  - Request body validation (incoming JSON)
  - Response serialization (outgoing JSON)
  - Internal data transfer objects

These are separate from ORM models intentionally:
API contracts should be decoupled from database structure.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator


# ─── Enumerations ─────────────────────────────────────────────────────────

class NodeType(str, Enum):
    SOURCE = "source"
    TRANSFORMATION = "transformation"
    SINK = "sink"

class OperationType(str, Enum):
    FILTER = "filter"
    JOIN = "join"
    AGGREGATION = "aggregation"
    UNION = "union"
    PROJECTION = "projection"
    SORT = "sort"
    DEDUPLICATE = "deduplicate"
    WRITE = "write"
    READ = "read"
    CUSTOM = "custom"


# ─── Node Schemas ─────────────────────────────────────────────────────────

class NodeInput(BaseModel):
    """Input schema for a single DAG node."""
    id: str = Field(..., description="Unique node identifier (e.g., 'raw_orders')")
    name: Optional[str] = Field(None, description="Display name; defaults to id if omitted")
    type: NodeType = Field(NodeType.TRANSFORMATION, description="Node classification")
    operation: Optional[str] = Field(None, description="Transformation operation type")
    description: Optional[str] = Field(None, description="Human-readable description")
    schema_info: Optional[Dict[str, Any]] = Field(
        None,
        description="Column-level metadata: {col_name: {type, description, source_col}}"
    )
    tags: Optional[List[str]] = Field(default_factory=list)
    version: Optional[str] = Field(None, description="Dataset version or timestamp")

    @field_validator("name", mode="before")
    @classmethod
    def default_name(cls, v, info):
        """If name not provided, use id as display name."""
        return v or info.data.get("id", "unknown")


class NodeResponse(BaseModel):
    """Response schema for a node, enriched with internal metadata."""
    id: str
    name: str
    type: str
    operation: Optional[str] = None
    description: Optional[str] = None
    schema_info: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    version: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─── Edge Schemas ─────────────────────────────────────────────────────────

class EdgeInput(BaseModel):
    """Input schema for a directed edge in the DAG."""
    from_: str = Field(..., alias="from", description="Source node id")
    to: str = Field(..., description="Destination node id")
    relationship_type: Optional[str] = Field(None, description="e.g., 'produces', 'filters_into'")
    column_mapping: Optional[Dict[str, str]] = Field(
        None,
        description="Column-level lineage: {source_col: target_col}"
    )

    model_config = {"populate_by_name": True}


class EdgeResponse(BaseModel):
    """Response schema for an edge."""
    from_node: str
    to_node: str
    relationship_type: Optional[str] = None
    column_mapping: Optional[Dict[str, str]] = None


# ─── DAG Upload Schemas ────────────────────────────────────────────────────

class DAGInput(BaseModel):
    """
    Primary input schema for uploading a pipeline DAG.
    Validates the full graph structure before processing.
    """
    name: Optional[str] = Field("Unnamed Pipeline", description="Pipeline name")
    description: Optional[str] = Field(None, description="Pipeline description")
    nodes: List[NodeInput] = Field(..., min_length=1, description="List of pipeline nodes")
    edges: List[EdgeInput] = Field(default_factory=list, description="List of directed edges")
    version: Optional[int] = Field(1, description="DAG version number")

    @field_validator("nodes")
    @classmethod
    def validate_unique_node_ids(cls, nodes):
        """Ensure no duplicate node IDs in the input."""
        ids = [n.id for n in nodes]
        if len(ids) != len(set(ids)):
            duplicates = [id_ for id_ in ids if ids.count(id_) > 1]
            raise ValueError(f"Duplicate node IDs found: {list(set(duplicates))}")
        return nodes

    @field_validator("edges")
    @classmethod
    def validate_edges(cls, edges, info):
        """Validate that edge endpoints reference existing nodes."""
        if "nodes" not in info.data:
            return edges
        node_ids = {n.id for n in info.data["nodes"]}
        for edge in edges:
            if edge.from_ not in node_ids:
                raise ValueError(f"Edge references unknown source node: '{edge.from_}'")
            if edge.to not in node_ids:
                raise ValueError(f"Edge references unknown destination node: '{edge.to}'")
        return edges


class DAGResponse(BaseModel):
    """Response returned after a successful DAG upload."""
    dag_id: str
    name: str
    version: int
    node_count: int
    edge_count: int
    created_at: datetime
    message: str = "DAG uploaded and processed successfully"


# ─── Lineage Response Schemas ─────────────────────────────────────────────

class LineagePath(BaseModel):
    """Represents a single path through the lineage graph."""
    path: List[str] = Field(description="Ordered list of node IDs from root to target")
    length: int = Field(description="Number of hops in path")


class LineageResponse(BaseModel):
    """
    Standard response for any lineage query.
    Contains the subgraph (nodes + edges) plus traversal paths.
    """
    query_node: str
    lineage_type: str                        # upstream | downstream | full | impact
    nodes: List[NodeResponse]
    edges: List[EdgeResponse]
    paths: List[LineagePath]
    depth: int = Field(description="Maximum lineage depth found")
    node_count: int
    computed_at: datetime = Field(default_factory=datetime.utcnow)
    from_cache: bool = False


class ImpactAnalysisResponse(BaseModel):
    """
    Response for impact analysis — which nodes are affected if a node fails.
    Includes risk scoring per affected node.
    """
    failed_node: str
    directly_affected: List[str]             # immediate downstream neighbors
    transitively_affected: List[str]         # all downstream descendants
    nodes: List[NodeResponse]
    edges: List[EdgeResponse]
    impact_score: float = Field(
        description="0-1 score: ratio of total nodes affected vs total DAG nodes"
    )
    risk_level: str = Field(description="LOW | MEDIUM | HIGH | CRITICAL")
    computed_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Column Lineage ────────────────────────────────────────────────────────

class ColumnLineage(BaseModel):
    """Column-level lineage tracing for a specific column."""
    target_column: str
    source_columns: List[Dict[str, str]]     # [{node_id, column_name}]
    transformation_path: List[str]           # node IDs in traversal order


# ─── DAG List / Summary ────────────────────────────────────────────────────

class DAGSummary(BaseModel):
    """Lightweight summary of a stored DAG (for listing)."""
    dag_id: str
    name: str
    version: int
    node_count: int
    edge_count: int
    created_at: datetime


class DAGListResponse(BaseModel):
    """Response for GET /dags endpoint."""
    dags: List[DAGSummary]
    total: int


# ─── Validation Error Detail ───────────────────────────────────────────────

class ValidationErrorDetail(BaseModel):
    """Structured error detail for DAG validation failures."""
    error_type: str
    message: str
    affected_nodes: Optional[List[str]] = None
    cycle_path: Optional[List[str]] = None   # populated if cyclic graph detected
