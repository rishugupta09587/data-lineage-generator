"""
models/db_models.py
-------------------
SQLAlchemy ORM table definitions.
These map directly to database tables.
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey,
    Integer, JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from database import Base


class DAGRecord(Base):
    """
    Stores uploaded DAG metadata.
    Each upload creates a new versioned DAG record.
    """
    __tablename__ = "dags"

    id = Column(String(36), primary_key=True)           # UUID
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(Integer, default=1)                 # for versioned DAG support
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    raw_json = Column(JSON, nullable=True)               # store original input for replay

    # Relationships - cascade delete ensures nodes/edges removed with DAG
    nodes = relationship("NodeRecord", back_populates="dag", cascade="all, delete-orphan")
    edges = relationship("EdgeRecord", back_populates="dag", cascade="all, delete-orphan")


class NodeRecord(Base):
    """
    Represents a node in the data pipeline DAG.
    Could be a source dataset, transformation step, or sink.
    """
    __tablename__ = "nodes"

    id = Column(String(36), primary_key=True)            # UUID (internal)
    dag_id = Column(String(36), ForeignKey("dags.id", ondelete="CASCADE"), nullable=False)
    node_id = Column(String(255), nullable=False)        # user-defined ID (e.g., "raw_orders")
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)             # source | transformation | sink
    operation = Column(String(100), nullable=True)        # filter | join | aggregation | etc.
    description = Column(Text, nullable=True)
    schema_info = Column(JSON, nullable=True)             # column-level metadata
    tags = Column(JSON, nullable=True)                    # user-defined tags
    created_at = Column(DateTime, default=datetime.utcnow)
    version = Column(String(50), nullable=True)           # data version/timestamp

    dag = relationship("DAGRecord", back_populates="nodes")

    __table_args__ = (
        # A node_id must be unique within a DAG
        UniqueConstraint("dag_id", "node_id", name="uq_dag_node"),
        # Fast lookup by dag_id
        Index("ix_nodes_dag_id", "dag_id"),
    )


class EdgeRecord(Base):
    """
    Represents a directed edge (data flow) between two nodes.
    from_node → to_node means data flows FROM source TO destination.
    """
    __tablename__ = "edges"

    id = Column(String(36), primary_key=True)
    dag_id = Column(String(36), ForeignKey("dags.id", ondelete="CASCADE"), nullable=False)
    from_node = Column(String(255), nullable=False)      # source node_id
    to_node = Column(String(255), nullable=False)        # destination node_id
    relationship_type = Column(String(100), nullable=True)  # e.g., "produces", "filters"
    column_mapping = Column(JSON, nullable=True)         # column-level lineage mapping

    dag = relationship("DAGRecord", back_populates="edges")

    __table_args__ = (
        Index("ix_edges_dag_id", "dag_id"),
        Index("ix_edges_from_node", "from_node"),
        Index("ix_edges_to_node", "to_node"),
    )


class LineageCacheRecord(Base):
    """
    Caches lineage computation results to avoid re-traversal on repeated queries.
    Cache key = dag_id + node_id + lineage_type.
    """
    __tablename__ = "lineage_cache"

    id = Column(String(36), primary_key=True)
    dag_id = Column(String(36), nullable=False)
    node_id = Column(String(255), nullable=False)
    lineage_type = Column(String(50), nullable=False)    # upstream | downstream | full | impact
    result_json = Column(JSON, nullable=False)
    computed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("dag_id", "node_id", "lineage_type", name="uq_lineage_cache"),
        Index("ix_cache_dag_node", "dag_id", "node_id"),
    )
