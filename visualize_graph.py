#!/usr/bin/env python3

import os
import sys
import matplotlib.pyplot as plt
from utils import VerilogKnowledgeGraph, ensure_checkpoint_dir


def main():
    """Main function to load and visualize the graph"""
    
    graph_path = sys.argv[1]

    # Load the graph from the JSON file
    graph = VerilogKnowledgeGraph.load_from_json(graph_path)
    
    if not graph or not hasattr(graph, 'G') or graph.G.number_of_nodes() == 0:
        print(f"Error: Failed to load a valid graph from {graph_path}")
        return 1
    
    print(f"Graph loaded successfully. Contains {graph.G.number_of_nodes()} nodes and {graph.G.number_of_edges()} edges.")
    
    graph.visualize_graph()
    
    return 0


if __name__ == '__main__':
    exit(main())