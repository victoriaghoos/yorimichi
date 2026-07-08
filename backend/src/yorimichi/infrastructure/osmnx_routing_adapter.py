"""
Infrastructure adapter: translates networkx's (u, v, data) graph structure
into calls against the pure Domain routing logic.
"""

from yorimichi.domain.entities import Node, Edge
from yorimichi.domain.routing import calculate_edge_cost, calculate_heuristic


def _node_from_graph(graph, node_id) -> Node:
    data = graph.nodes[node_id]
    return Node(id=str(node_id), lat=data["y"], lon=data["x"])


def make_edge_weight_fn(graph, scenic_provider):
    def weight_fn(u, v, data):
        edge = Edge(
            from_node=_node_from_graph(graph, u),
            to_node=_node_from_graph(graph, v),
            length=data.get("length", 1.0),
            highway_tag=data.get("highway"),
        )
        return calculate_edge_cost(edge, scenic_provider)
    return weight_fn


def make_heuristic_fn(graph, best_case_penalty=None):
    """Returns a networkx-compatible heuristic function, translating node IDs into Domain Nodes."""
    kwargs = {} if best_case_penalty is None else {"best_case_penalty": best_case_penalty}

    def heuristic_fn(u, v):
        from_node = _node_from_graph(graph, u)
        to_node = _node_from_graph(graph, v)
        return calculate_heuristic(from_node, to_node, **kwargs)
    return heuristic_fn