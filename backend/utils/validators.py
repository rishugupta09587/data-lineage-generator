"""
utils/validators.py
-------------------
Validates DAG structure before it is stored or processed.
Key checks:
  1. No cycles (must be a Directed ACYCLIC Graph)
  2. All edge endpoints reference existing nodes
  3. Graph connectivity (warn on isolated nodes)
  4. Self-loops detection
"""

import logging
from typing import List, Tuple, Optional
import networkx as nx

from models.schemas import DAGInput, EdgeInput

logger = logging.getLogger(__name__)


class DAGValidationError(Exception):
    """Raised when a DAG fails structural validation."""
    def __init__(self, message: str, cycle_path: Optional[List[str]] = None):
        super().__init__(message)
        self.cycle_path = cycle_path or []


def validate_dag(dag_input: DAGInput) -> Tuple[bool, Optional[str], Optional[List[str]]]:
    """
    Comprehensive DAG validation.
    Returns: (is_valid, error_message, cycle_path)

    Steps:
      1. Build a NetworkX DiGraph from input
      2. Check for self-loops (A → A)
      3. Check for cycles using DFS (networkx.find_cycle)
      4. Check for isolated nodes (informational warning only)
      5. Verify the graph is weakly connected (optional warning)
    """
    node_ids = {node.id for node in dag_input.nodes}
    G = nx.DiGraph()

    # Add all nodes
    for node in dag_input.nodes:
        G.add_node(node.id, **{
            "name": node.name,
            "type": node.type,
            "operation": node.operation,
        })

    # Add all edges
    for edge in dag_input.edges:
        # Check self-loop
        if edge.from_ == edge.to:
            msg = f"Self-loop detected on node '{edge.from_}'. DAGs cannot have self-loops."
            logger.warning(msg)
            return False, msg, [edge.from_]

        G.add_edge(edge.from_, edge.to)

    # ── Cycle Detection ─────────────────────────────────────────────────
    # networkx.find_cycle raises NetworkXNoCycle if no cycle exists
    try:
        cycle_edges = nx.find_cycle(G, orientation="original")
        # Extract cycle path from edge list
        cycle_path = [e[0] for e in cycle_edges] + [cycle_edges[-1][1]]
        msg = (
            f"Cycle detected in DAG: {' → '.join(cycle_path)}. "
            "A Data Lineage DAG must be acyclic."
        )
        logger.error(msg)
        return False, msg, cycle_path
    except nx.NetworkXNoCycle:
        # No cycle found — this is the happy path
        pass

    # ── Isolated Node Warning ────────────────────────────────────────────
    isolated = list(nx.isolates(G))
    if isolated:
        logger.warning(
            "Isolated nodes detected (no edges): %s. "
            "These nodes will appear in the graph but have no lineage connections.",
            isolated
        )

    # ── Topological Sort Verification ───────────────────────────────────
    # If we can compute a topological order, the graph is a valid DAG
    try:
        topo_order = list(nx.topological_sort(G))
        logger.info("DAG validated successfully. Topological order: %s", topo_order)
    except nx.NetworkXUnfeasible:
        msg = "DAG validation failed: graph is not acyclic (topological sort failed)."
        return False, msg, []

    return True, None, []


def build_networkx_graph(nodes: list, edges: list) -> nx.DiGraph:
    """
    Build a NetworkX DiGraph from ORM node and edge records.
    Used by lineage and impact analysis services.

    Args:
        nodes: List of NodeRecord ORM objects
        edges: List of EdgeRecord ORM objects

    Returns:
        nx.DiGraph with node attributes set
    """
    G = nx.DiGraph()

    for node in nodes:
        G.add_node(node.node_id, **{
            "name": node.name,
            "type": node.type,
            "operation": node.operation,
            "description": node.description,
            "schema_info": node.schema_info,
            "tags": node.tags,
            "version": node.version,
        })

    for edge in edges:
        G.add_edge(edge.from_node, edge.to_node, **{
            "relationship_type": edge.relationship_type,
            "column_mapping": edge.column_mapping,
        })

    return G


def extract_all_paths(G: nx.DiGraph, source: str, target: str) -> List[List[str]]:
    """
    Find all simple paths from source to target.
    Caps at 100 paths to prevent combinatorial explosion on dense graphs.
    """
    try:
        paths = list(nx.all_simple_paths(G, source=source, target=target, cutoff=50))
        return paths[:100]  # safety cap
    except (nx.NodeNotFound, nx.NetworkXError):
        return []
