import networkx as nx

from yorimichi.application.plan_route_use_case import PlanRouteResult
from yorimichi.domain.entities import Route
from yorimichi.infrastructure.visualization import _normalize_route_node_ids, print_route_comparison


def test_print_route_comparison_outputs_expected_format(capsys):
    """Confirms the printed comparison includes both lengths and the correct diff sign."""
    result = PlanRouteResult(
        baseline_route=Route(node_ids=("1", "2"), length=100.0),
        scenic_route=Route(node_ids=("1", "3", "2"), length=150.0),
        baseline_coordinates=((35.0, 135.0), (35.001, 135.001)),
        scenic_coordinates=((35.0, 135.0), (35.0005, 135.0005), (35.001, 135.001)),
    )

    print_route_comparison("Test Label", result)

    captured = capsys.readouterr()
    assert "Test Label" in captured.out
    assert "baseline=100.0m" in captured.out
    assert "scenic=150.0m" in captured.out
    assert "diff=+50.0m" in captured.out


def test_normalize_route_node_ids_returns_int_keys_for_osmnx_style_graph():
    graph = nx.MultiDiGraph(crs="EPSG:4326")
    graph.add_node(1, y=35.0, x=135.0)
    graph.add_node(2, y=35.001, x=135.001)

    normalized = _normalize_route_node_ids(graph, ("1", "2"))

    assert normalized == [1, 2]


def test_normalize_route_node_ids_keeps_string_keys_for_postgis_style_graph():
    graph = nx.MultiDiGraph(crs="EPSG:4326")
    graph.add_node("1", y=35.0, x=135.0)
    graph.add_node("2", y=35.001, x=135.001)

    normalized = _normalize_route_node_ids(graph, ("1", "2"))

    assert normalized == ["1", "2"]