"""
Infrastructure adapter: translates networkx's (u, v, data) graph structure
into calls against the pure Domain routing logic.
"""

from yorimichi.domain.entities import Node, Edge
from yorimichi.domain.routing import calculate_edge_cost, calculate_heuristic


def _node_from_graph(graph, node_id) -> Node:
    data = graph.nodes[node_id]
    return Node(id=str(node_id), lat=data["y"], lon=data["x"])


def make_edge_weight_fn(graph, scenic_index):
    def _edge_attr_dicts(edge_dict):
        # For MultiDiGraph, networkx passes {edge_key: attrs}. For plain graphs,
        # it may pass attrs directly.
        if "length" in edge_dict or "highway" in edge_dict:
            return [edge_dict]
        return [data for data in edge_dict.values() if isinstance(data, dict)]

    def weight_fn(u, v, edge_dict):
        from_node = _node_from_graph(graph, u)
        to_node = _node_from_graph(graph, v)

        return min(
            calculate_edge_cost(
                Edge(
                    from_node=from_node,
                    to_node=to_node,
                    length=data.get("length", 1.0),
                    highway_tag=data.get("highway"),
                ),
                scenic_index,
            )
            for data in _edge_attr_dicts(edge_dict)
        )

    return weight_fn


def make_heuristic_fn(graph, best_case_penalty=None):
    """Returns a networkx-compatible heuristic function, translating node IDs into Domain Nodes."""
    kwargs = {} if best_case_penalty is None else {"best_case_penalty": best_case_penalty}

    def heuristic_fn(u, v):
        from_node = _node_from_graph(graph, u)
        to_node = _node_from_graph(graph, v)
        return calculate_heuristic(from_node, to_node, **kwargs)
    return heuristic_fn