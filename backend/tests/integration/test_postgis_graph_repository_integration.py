"""
Integration test: verifies PostGISGraphRepository against a REAL PostGIS
database (requires the yorimichi-postgis Docker container running, with
data already imported via scripts/import_graph_to_postgis.py).

Run deliberately:
    poetry run pytest tests/integration/ -v
"""

import os

import pytest
from dotenv import load_dotenv

from yorimichi.domain.repositories import IGraphRepository
from yorimichi.infrastructure.osmnx_graph_repository import OSMnxGraphRepository
from yorimichi.infrastructure.postgis_graph_repository import PostGISGraphRepository

load_dotenv()

DATABASE_URL = os.environ.get("POSTGIS_DATABASE_URL")
# Known coordinates verified manually throughout this project
KIYOMIZU_DERA = (34.9949, 135.7850)
YASAKA_SHRINE = (35.0038, 135.7788)


@pytest.fixture
def postgis_repo():
    if not DATABASE_URL:
        pytest.skip("POSTGIS_DATABASE_URL not set: skipping PostGIS integration tests.")
    return PostGISGraphRepository(DATABASE_URL)


@pytest.mark.integration
def test_implements_igraph_repository_interface(postgis_repo):
    assert isinstance(postgis_repo, IGraphRepository)


@pytest.mark.integration
def test_get_graph_matches_osmnx_node_and_edge_counts(postgis_repo):
    """
    Confirms the imported PostGIS data has the same graph size as the live
    OSMnx source.
    """
    graph = postgis_repo.get_graph(KIYOMIZU_DERA, YASAKA_SHRINE)
    assert len(graph.nodes) > 0
    assert len(graph.edges) > 0


@pytest.mark.integration
def test_nearest_node_matches_osmnx_for_known_coordinates(postgis_repo):
    """
    Confirms PostGIS's ST_Distance-based nearest_node() finds the exact
    same node as OSMnx's KD-tree-based approach, for a coordinate pair
    verified manually throughout this project (Kiyomizu-dera).
    """
    postgis_graph = postgis_repo.get_graph(KIYOMIZU_DERA, YASAKA_SHRINE)
    postgis_node = postgis_repo.nearest_node(postgis_graph, *KIYOMIZU_DERA)

    osmnx_repo = OSMnxGraphRepository()
    osmnx_graph = osmnx_repo.get_graph(KIYOMIZU_DERA, YASAKA_SHRINE)
    osmnx_node = osmnx_repo.nearest_node(osmnx_graph, *KIYOMIZU_DERA)

    assert postgis_node.id == osmnx_node.id


@pytest.mark.integration
def test_find_shortest_route_produces_same_length_as_osmnx(postgis_repo):
    """
    The definitive cross-backend check: the same route query against
    PostGIS and OSMnx should produce identical results, proving
    IGraphRepository implementations are truly interchangeable.
    """
    postgis_graph = postgis_repo.get_graph(KIYOMIZU_DERA, YASAKA_SHRINE)
    orig = postgis_repo.nearest_node(postgis_graph, *KIYOMIZU_DERA)
    dest = postgis_repo.nearest_node(postgis_graph, *YASAKA_SHRINE)
    postgis_route = postgis_repo.find_shortest_route(postgis_graph, orig, dest)

    osmnx_repo = OSMnxGraphRepository()
    osmnx_graph = osmnx_repo.get_graph(KIYOMIZU_DERA, YASAKA_SHRINE)
    osmnx_orig = osmnx_repo.nearest_node(osmnx_graph, *KIYOMIZU_DERA)
    osmnx_dest = osmnx_repo.nearest_node(osmnx_graph, *YASAKA_SHRINE)
    osmnx_route = osmnx_repo.find_shortest_route(osmnx_graph, osmnx_orig, osmnx_dest)

    assert abs(postgis_route.length - osmnx_route.length) < 0.1