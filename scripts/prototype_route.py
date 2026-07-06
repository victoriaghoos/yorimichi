import osmnx as ox

PLACE = "Higashiyama Ward, Kyoto, Japan"

def main():
    print(f"Fetching graph for: {PLACE}")
    graph = ox.graph_from_place(PLACE, network_type="walk")
    print(f"Nodes: {len(graph.nodes)}, Edges: {len(graph.edges)}")

    ox.plot_graph(graph, node_size=5, edge_linewidth=0.5)

if __name__ == "__main__":
    main()