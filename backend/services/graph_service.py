"""
services/graph_service.py
--------------------------
Core graph engine using NetworkX.

Provides:
  - Upstream lineage (BFS/DFS backward from a node)
  - Downstream lineage (BFS/DFS forward from a node)
  - Full lineage (both directions combined)
  - Topological ordering
  - Critical path detection
  - Graph statistics

Design: Stateless service — receives a pre-built nx.DiGraph, returns results.
This keeps the service testable and independent of database concerns.
"""

import logging
from typing import List, Dict, Any, Tuple, Set, Optional
from collections import deque
import networkx as nx

logger = logging.getLogger(__name__)


class GraphTraversalService:
    """
    Wraps a NetworkX DiGraph with lineage-specific traversal methods.
    All methods are pure functions over the graph — no side effects.
    """

    def __init__(self, G: nx.DiGraph):
        """
        Args:
            G: A NetworkX DiGraph. Nodes should have attribute dicts
               containing name, type, operation, etc.
        """
        self.G = G
        self._validate_graph()

    def _validate_graph(self):
        """Sanity check on the graph before any operation."""
        if not isinstance(self.G, nx.DiGraph):
            raise TypeError("Graph must be a NetworkX DiGraph")
        node_count = self.G.number_of_nodes()
        edge_count = self.G.number_of_edges()
        logger.debug("GraphTraversalService initialized: %d nodes, %d edges",
                     node_count, edge_count)

    def node_exists(self, node_id: str) -> bool:
        return node_id in self.G

    def get_node_attributes(self, node_id: str) -> Dict[str, Any]:
        """Retrieve all metadata attributes for a node."""
        if not self.node_exists(node_id):
            return {}
        return dict(self.G.nodes[node_id])

    # ─── Upstream Lineage (Ancestors) ────────────────────────────────────

    def get_upstream(self, node_id: str) -> Tuple[Set[str], List[Tuple[str, str]]]:
        """
        Find all ancestor nodes (nodes that directly or indirectly
        produce data consumed by node_id).

        Algorithm: BFS on the REVERSED graph from node_id.
        Reversing lets us use standard BFS as if walking "backwards".

        Returns:
            (ancestor_node_ids, subgraph_edges)
        """
        if not self.node_exists(node_id):
            raise ValueError(f"Node '{node_id}' not found in graph")

        # ancestors() uses BFS on reversed graph internally
        ancestors: Set[str] = nx.ancestors(self.G, node_id)

        # Build the subgraph edges (only edges within the ancestor set + target node)
        subgraph_nodes = ancestors | {node_id}
        subgraph = self.G.subgraph(subgraph_nodes)
        edges = list(subgraph.edges())

        logger.debug("Upstream of '%s': %d ancestors", node_id, len(ancestors))
        return ancestors, edges

    # ─── Downstream Lineage (Descendants) ────────────────────────────────

    def get_downstream(self, node_id: str) -> Tuple[Set[str], List[Tuple[str, str]]]:
        """
        Find all descendant nodes (nodes that consume data produced
        directly or indirectly by node_id).

        Algorithm: BFS on the graph from node_id.

        Returns:
            (descendant_node_ids, subgraph_edges)
        """
        if not self.node_exists(node_id):
            raise ValueError(f"Node '{node_id}' not found in graph")

        descendants: Set[str] = nx.descendants(self.G, node_id)
        subgraph_nodes = descendants | {node_id}
        subgraph = self.G.subgraph(subgraph_nodes)
        edges = list(subgraph.edges())

        logger.debug("Downstream of '%s': %d descendants", node_id, len(descendants))
        return descendants, edges

    # ─── Full Lineage (Both Directions) ───────────────────────────────────

    def get_full_lineage(self, node_id: str) -> Tuple[Set[str], List[Tuple[str, str]]]:
        """
        Combine upstream and downstream into a complete lineage subgraph.
        Useful for understanding a node's full context in the pipeline.

        Returns:
            (all_related_nodes, subgraph_edges)
        """
        ancestors, _ = self.get_upstream(node_id)
        descendants, _ = self.get_downstream(node_id)
        all_nodes = ancestors | {node_id} | descendants
        subgraph = self.G.subgraph(all_nodes)
        edges = list(subgraph.edges())

        logger.debug("Full lineage of '%s': %d total nodes", node_id, len(all_nodes))
        return all_nodes, edges

    # ─── Path Finding ─────────────────────────────────────────────────────

    def find_all_paths_to(self, node_id: str) -> List[List[str]]:
        """
        Find all paths that END at node_id (i.e., all root-to-node paths).
        Useful for upstream path tracing.
        """
        roots = [n for n in self.G.nodes if self.G.in_degree(n) == 0]
        all_paths = []
        for root in roots:
            try:
                paths = list(nx.all_simple_paths(
                    self.G, source=root, target=node_id, cutoff=50
                ))
                all_paths.extend(paths)
            except nx.NetworkXError:
                continue

        # Sort by path length (shortest first) for readability
        all_paths.sort(key=len)
        return all_paths[:100]  # Safety cap against combinatorial explosion

    def find_all_paths_from(self, node_id: str) -> List[List[str]]:
        """
        Find all paths that START at node_id (node-to-sink paths).
        Useful for impact/downstream analysis.
        """
        sinks = [n for n in self.G.nodes if self.G.out_degree(n) == 0]
        all_paths = []
        for sink in sinks:
            try:
                paths = list(nx.all_simple_paths(
                    self.G, source=node_id, target=sink, cutoff=50
                ))
                all_paths.extend(paths)
            except nx.NetworkXError:
                continue

        all_paths.sort(key=len)
        return all_paths[:100]

    # ─── Impact Analysis ──────────────────────────────────────────────────

    def compute_impact(self, node_id: str) -> Dict[str, Any]:
        """
        Impact Analysis: If node_id fails, what nodes are affected?

        Logic:
          - Direct impact: immediate successors (out_neighbors)
          - Transitive impact: all descendants
          - Impact score: len(descendants) / total_nodes
          - Risk level: based on impact score thresholds

        Returns dict with impact details.
        """
        if not self.node_exists(node_id):
            raise ValueError(f"Node '{node_id}' not found in graph")

        total_nodes = self.G.number_of_nodes()

        # Direct (1-hop) impact
        direct_affected = list(self.G.successors(node_id))

        # Transitive (all downstream) impact
        transitive_affected = list(nx.descendants(self.G, node_id))

        # Subgraph for affected nodes
        affected_set = set(transitive_affected) | {node_id}
        subgraph = self.G.subgraph(affected_set)
        affected_edges = list(subgraph.edges())

        # Impact score: fraction of total pipeline affected
        impact_score = len(transitive_affected) / max(total_nodes - 1, 1)

        # Risk classification
        if impact_score >= 0.75:
            risk_level = "CRITICAL"
        elif impact_score >= 0.5:
            risk_level = "HIGH"
        elif impact_score >= 0.25:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return {
            "failed_node": node_id,
            "directly_affected": direct_affected,
            "transitively_affected": transitive_affected,
            "affected_edges": affected_edges,
            "impact_score": round(impact_score, 4),
            "risk_level": risk_level,
            "total_pipeline_nodes": total_nodes,
        }

    # ─── Column-Level Lineage Simulation ─────────────────────────────────

    def trace_column_lineage(
        self, target_node: str, target_column: str
    ) -> Dict[str, Any]:
        """
        Simulate column-level lineage by tracing a column backwards
        through nodes that have column_mapping metadata on their edges.

        In a real system this would use actual schema catalog data.
        Here we simulate it using edge column_mapping attributes.
        """
        ancestors, edges = self.get_upstream(target_node)
        column_chain = []
        source_columns = []

        # Walk edges in reverse topological order
        for u, v, data in self.G.edges(data=True):
            if v == target_node or (u in ancestors and v in ancestors | {target_node}):
                col_mapping = data.get("column_mapping") or {}
                for src_col, tgt_col in col_mapping.items():
                    if tgt_col == target_column:
                        source_columns.append({"node_id": u, "column_name": src_col})
                        column_chain.append(u)

        return {
            "target_node": target_node,
            "target_column": target_column,
            "source_columns": source_columns,
            "transformation_path": column_chain,
        }

    # ─── Graph Statistics ─────────────────────────────────────────────────

    def get_graph_stats(self) -> Dict[str, Any]:
        """
        Return summary statistics about the graph.
        Useful for the UI overview panel.
        """
        sources = [n for n in self.G.nodes if self.G.in_degree(n) == 0]
        sinks = [n for n in self.G.nodes if self.G.out_degree(n) == 0]

        # Longest path = critical path length
        try:
            longest_path_length = nx.dag_longest_path_length(self.G)
            critical_path = nx.dag_longest_path(self.G)
        except Exception:
            longest_path_length = 0
            critical_path = []

        return {
            "node_count": self.G.number_of_nodes(),
            "edge_count": self.G.number_of_edges(),
            "source_count": len(sources),
            "sink_count": len(sinks),
            "sources": sources,
            "sinks": sinks,
            "longest_path_length": longest_path_length,
            "critical_path": critical_path,
            "is_connected": nx.is_weakly_connected(self.G) if self.G.number_of_nodes() > 0 else False,
            "density": round(nx.density(self.G), 4),
        }

    def get_topological_order(self) -> List[str]:
        """Return nodes in topological sort order (source to sink)."""
        return list(nx.topological_sort(self.G))
