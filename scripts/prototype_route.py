import osmnx as ox
import networkx as nx

PLACE = "Higashiyama Ward, Kyoto, Japan"

def main():
    print(f"Fetching graph for: {PLACE}")
    graph = ox.graph_from_place(PLACE, network_type="walk")
    print(f"Nodes: {len(graph.nodes)}, Edges: {len(graph.edges)}")

    orig_point = (34.9949, 135.7850)  # Kiyomizu-dera
    dest_point = (35.0038, 135.7788)  # Yasaka Shrine

    orig_node = ox.nearest_nodes(graph, orig_point[1], orig_point[0])
    dest_node = ox.nearest_nodes(graph, dest_point[1], dest_point[0])

    route = nx.shortest_path(graph, orig_node, dest_node, weight="length")
    route_length = nx.shortest_path_length(graph, orig_node, dest_node, weight="length")

    print(f"Route has {len(route)} nodes, total length: {route_length:.1f} meters")

    ox.plot_graph_route(graph, route, route_linewidth=3, node_size=0)

if __name__ == "__main__":
    main()