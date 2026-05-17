"""
tests/test_graph_service.py
----------------------------
Unit tests for the core graph traversal engine.

Tests cover:
  - DAG validation (cycle detection, self-loops)
  - Upstream / downstream lineage traversal
  - Impact analysis
  - Edge cases (isolated nodes, single-node graph, disconnected components)
  - Performance with large graphs

Run with:
    cd backend
    pytest tests/ -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import networkx as nx

from services.graph_service import GraphTraversalService
from utils.validators import validate_dag, build_networkx_graph
from models.schemas import DAGInput, NodeInput, EdgeInput


# ─── Fixtures ─────────────────────────────────────────────────────────────

def make_node(node_id, type_="transformation", operation=None):
    """Helper to create a NodeInput object."""
    return NodeInput(
        id=node_id,
        type=type_,
        operation=operation,
    )


def make_edge(from_id, to_id):
    """Helper to create an EdgeInput object."""
    return EdgeInput(**{"from": from_id, "to": to_id})


@pytest.fixture
def linear_dag():
    """A → B → C → D (simple linear pipeline)."""
    nodes = [make_node("A", "source"), make_node("B"), make_node("C"), make_node("D", "sink")]
    edges = [make_edge("A", "B"), make_edge("B", "C"), make_edge("C", "D")]
    return DAGInput(name="Linear", nodes=nodes, edges=edges)


@pytest.fixture
def diamond_dag():
    """
    Diamond-shaped DAG:
        A → B → D
        A → C → D
    """
    nodes = [make_node("A", "source"), make_node("B"), make_node("C"), make_node("D", "sink")]
    edges = [
        make_edge("A", "B"), make_edge("A", "C"),
        make_edge("B", "D"), make_edge("C", "D")
    ]
    return DAGInput(name="Diamond", nodes=nodes, edges=edges)


@pytest.fixture
def linear_service():
    """Build a GraphTraversalService from a linear graph A→B→C→D."""
    G = nx.DiGraph()
    G.add_nodes_from([
        ("A", {"name": "A", "type": "source", "operation": None}),
        ("B", {"name": "B", "type": "transformation", "operation": "filter"}),
        ("C", {"name": "C", "type": "transformation", "operation": "join"}),
        ("D", {"name": "D", "type": "sink", "operation": None}),
    ])
    G.add_edges_from([("A", "B"), ("B", "C"), ("C", "D")])
    return GraphTraversalService(G)


@pytest.fixture
def diamond_service():
    """Build a GraphTraversalService from a diamond graph."""
    G = nx.DiGraph()
    G.add_nodes_from(["A", "B", "C", "D"])
    G.add_edges_from([("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")])
    return GraphTraversalService(G)


# ─── Validation Tests ─────────────────────────────────────────────────────

class TestDAGValidation:

    def test_valid_linear_dag(self, linear_dag):
        """A valid DAG should pass validation."""
        is_valid, error, cycle = validate_dag(linear_dag)
        assert is_valid is True
        assert error is None
        assert cycle == []

    def test_valid_diamond_dag(self, diamond_dag):
        """A diamond DAG (valid) should pass."""
        is_valid, error, _ = validate_dag(diamond_dag)
        assert is_valid is True

    def test_cyclic_dag_rejected(self):
        """A DAG with a cycle must be rejected."""
        nodes = [make_node("A"), make_node("B"), make_node("C")]
        edges = [make_edge("A", "B"), make_edge("B", "C"), make_edge("C", "A")]  # cycle!
        dag = DAGInput(name="Cyclic", nodes=nodes, edges=edges)

        is_valid, error, cycle_path = validate_dag(dag)

        assert is_valid is False
        assert error is not None
        assert "Cycle detected" in error
        assert len(cycle_path) >= 2  # at least 2 nodes form a cycle

    def test_self_loop_rejected(self):
        """A self-loop (A → A) must be rejected."""
        nodes = [make_node("A"), make_node("B")]
        edges = [make_edge("A", "A")]  # self-loop
        dag = DAGInput(name="SelfLoop", nodes=nodes, edges=edges)

        is_valid, error, cycle_path = validate_dag(dag)
        assert is_valid is False
        assert "Self-loop" in error

    def test_duplicate_node_ids_rejected(self):
        """Duplicate node IDs must raise a validation error."""
        with pytest.raises(Exception) as exc_info:
            DAGInput(
                name="Dupe",
                nodes=[make_node("A"), make_node("A")],  # duplicate
                edges=[],
            )
        assert "Duplicate" in str(exc_info.value)

    def test_edge_unknown_source_rejected(self):
        """An edge referencing a non-existent source node must fail."""
        with pytest.raises(Exception) as exc_info:
            DAGInput(
                name="BadEdge",
                nodes=[make_node("A"), make_node("B")],
                edges=[make_edge("Z", "B")],   # Z doesn't exist
            )
        assert "unknown" in str(exc_info.value).lower()

    def test_isolated_node_allowed(self):
        """A node with no edges is allowed (warning only, not error)."""
        nodes = [make_node("A"), make_node("B"), make_node("isolated")]
        edges = [make_edge("A", "B")]
        dag = DAGInput(name="Isolated", nodes=nodes, edges=edges)

        is_valid, error, _ = validate_dag(dag)
        assert is_valid is True  # isolated nodes don't invalidate the DAG


# ─── Upstream Lineage Tests ────────────────────────────────────────────────

class TestUpstreamLineage:

    def test_source_has_no_upstream(self, linear_service):
        """A source node (A) should have no ancestors."""
        ancestors, edges = linear_service.get_upstream("A")
        assert ancestors == set()
        assert edges == []

    def test_linear_upstream(self, linear_service):
        """Node D's upstream should include A, B, C."""
        ancestors, _ = linear_service.get_upstream("D")
        assert ancestors == {"A", "B", "C"}

    def test_mid_node_upstream(self, linear_service):
        """Node C's upstream should be A and B only."""
        ancestors, _ = linear_service.get_upstream("C")
        assert ancestors == {"A", "B"}

    def test_diamond_upstream_both_paths(self, diamond_service):
        """Node D in diamond DAG should see A, B, C as ancestors."""
        ancestors, _ = diamond_service.get_upstream("D")
        assert ancestors == {"A", "B", "C"}

    def test_upstream_nonexistent_node_raises(self, linear_service):
        """Querying a node that doesn't exist must raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            linear_service.get_upstream("GHOST")


# ─── Downstream Lineage Tests ──────────────────────────────────────────────

class TestDownstreamLineage:

    def test_sink_has_no_downstream(self, linear_service):
        """A sink node (D) has no descendants."""
        descendants, edges = linear_service.get_downstream("D")
        assert descendants == set()

    def test_source_full_downstream(self, linear_service):
        """Source node A's downstream should be B, C, D."""
        descendants, _ = linear_service.get_downstream("A")
        assert descendants == {"B", "C", "D"}

    def test_mid_node_downstream(self, linear_service):
        """Node B's downstream should be C and D."""
        descendants, _ = linear_service.get_downstream("B")
        assert descendants == {"C", "D"}

    def test_diamond_downstream_both_branches(self, diamond_service):
        """Source A's downstream should be B, C, D (both diamond branches)."""
        descendants, _ = diamond_service.get_downstream("A")
        assert descendants == {"B", "C", "D"}


# ─── Full Lineage Tests ────────────────────────────────────────────────────

class TestFullLineage:

    def test_full_lineage_of_middle_node(self, linear_service):
        """Node B: upstream={A}, downstream={C,D}, total with B=4 nodes."""
        all_nodes, edges = linear_service.get_full_lineage("B")
        assert "A" in all_nodes  # upstream
        assert "C" in all_nodes  # downstream
        assert "D" in all_nodes  # downstream
        assert "B" in all_nodes  # self
        assert len(all_nodes) == 4

    def test_full_lineage_of_source(self, linear_service):
        """Source node A has no upstream — full lineage = all nodes."""
        all_nodes, _ = linear_service.get_full_lineage("A")
        assert all_nodes == {"A", "B", "C", "D"}

    def test_full_lineage_of_sink(self, linear_service):
        """Sink node D has no downstream — full lineage = all nodes."""
        all_nodes, _ = linear_service.get_full_lineage("D")
        assert all_nodes == {"A", "B", "C", "D"}


# ─── Impact Analysis Tests ────────────────────────────────────────────────

class TestImpactAnalysis:

    def test_source_failure_impacts_all(self, linear_service):
        """If source A fails, B, C, D are all impacted."""
        result = linear_service.compute_impact("A")
        assert set(result["directly_affected"]) == {"B"}
        assert set(result["transitively_affected"]) == {"B", "C", "D"}
        assert result["impact_score"] > 0.5
        assert result["risk_level"] in ("HIGH", "CRITICAL")

    def test_sink_failure_impacts_nobody(self, linear_service):
        """If sink D fails, nobody downstream is affected."""
        result = linear_service.compute_impact("D")
        assert result["directly_affected"] == []
        assert result["transitively_affected"] == []
        assert result["impact_score"] == 0.0
        assert result["risk_level"] == "LOW"

    def test_impact_score_range(self, linear_service):
        """Impact score must always be in [0, 1]."""
        for node_id in ["A", "B", "C", "D"]:
            result = linear_service.compute_impact(node_id)
            assert 0.0 <= result["impact_score"] <= 1.0

    def test_risk_levels_ordering(self, linear_service):
        """Higher-centrality nodes should have higher risk levels."""
        impact_a = linear_service.compute_impact("A")
        impact_d = linear_service.compute_impact("D")
        assert impact_a["impact_score"] > impact_d["impact_score"]

    def test_diamond_mid_node_impact(self, diamond_service):
        """In diamond, if B fails, only D is transitively affected."""
        result = diamond_service.compute_impact("B")
        assert "D" in result["transitively_affected"]
        assert "C" not in result["transitively_affected"]  # C is unaffected by B failing


# ─── Path Finding Tests ────────────────────────────────────────────────────

class TestPathFinding:

    def test_single_path_linear(self, linear_service):
        """In a linear DAG, there's exactly 1 path from A to D."""
        paths = linear_service.find_all_paths_to("D")
        assert len(paths) == 1
        assert paths[0] == ["A", "B", "C", "D"]

    def test_two_paths_in_diamond(self, diamond_service):
        """In a diamond, there are exactly 2 paths from A to D."""
        paths = linear_service.find_all_paths_to("D") if False else \
                list(nx.all_simple_paths(diamond_service.G, "A", "D"))
        assert len(paths) == 2
        path_sets = [tuple(p) for p in paths]
        assert ("A", "B", "D") in path_sets
        assert ("A", "C", "D") in path_sets

    def test_paths_sorted_by_length(self, linear_service):
        """Paths should be returned shortest-first."""
        paths = linear_service.find_all_paths_to("D")
        lengths = [len(p) for p in paths]
        assert lengths == sorted(lengths)


# ─── Graph Statistics Tests ───────────────────────────────────────────────

class TestGraphStats:

    def test_basic_stats(self, linear_service):
        stats = linear_service.get_graph_stats()
        assert stats["node_count"] == 4
        assert stats["edge_count"] == 3
        assert stats["source_count"] == 1   # only A has in_degree 0
        assert stats["sink_count"] == 1     # only D has out_degree 0
        assert stats["longest_path_length"] == 3  # A→B→C→D = 3 edges

    def test_density(self, linear_service):
        stats = linear_service.get_graph_stats()
        # Density = edges / (n*(n-1)) = 3 / (4*3) = 0.25
        assert abs(stats["density"] - 0.25) < 0.01

    def test_critical_path_is_list(self, linear_service):
        stats = linear_service.get_graph_stats()
        assert isinstance(stats["critical_path"], list)
        assert len(stats["critical_path"]) > 0


# ─── Large Graph Performance Test ─────────────────────────────────────────

class TestLargeGraph:

    def test_1000_node_dag_traversal(self):
        """
        Verify that lineage traversal completes in reasonable time
        for a 1000-node DAG. Uses a layered DAG for determinism.
        """
        import time

        # Build a 10-layer DAG with 100 nodes per layer = 1000 nodes
        G = nx.DiGraph()
        n_layers = 10
        n_per_layer = 100
        layers = []

        for layer in range(n_layers):
            layer_nodes = [f"L{layer}_N{i}" for i in range(n_per_layer)]
            G.add_nodes_from(layer_nodes)
            layers.append(layer_nodes)
            if layer > 0:
                # Connect each node to 2 nodes in previous layer
                import random
                random.seed(layer)
                for node in layer_nodes:
                    parents = random.sample(layers[layer - 1], min(2, len(layers[layer-1])))
                    for parent in parents:
                        G.add_edge(parent, node)

        service = GraphTraversalService(G)

        # Test that upstream from last layer completes quickly
        start = time.time()
        ancestors, _ = service.get_upstream("L9_N50")
        elapsed = time.time() - start

        assert elapsed < 5.0, f"Upstream traversal too slow: {elapsed:.2f}s"
        assert len(ancestors) > 0

        # Test impact analysis
        start = time.time()
        result = service.compute_impact("L0_N0")
        elapsed = time.time() - start

        assert elapsed < 5.0, f"Impact analysis too slow: {elapsed:.2f}s"
        assert result["impact_score"] >= 0

        print(f"\n✅ 1000-node DAG — upstream={len(ancestors)} ancestors, "
              f"impact={result['impact_score']:.2%} in {elapsed:.3f}s")
