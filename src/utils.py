#########
# GLOBALS
#########


import numpy as np
import networkx as nx
import random as rand
from tsp_solver.greedy import solve_tsp as solve
from graph_nets import utils_tf
from graph_nets import utils_np


#########
# HELPERS
#########


def create_random_graph(node_range=(5, 9), prob=0.25, weight_range=(1, 10)):
    n_nodes = rand.randint(*node_range)

    G = nx.complete_graph(n_nodes)
    H = G.copy()
    for u, v, w in G.edges(data=True):
        H[u][v]["weight"] = rand.randint(*weight_range)

        # u_deg, v_deg = H.degree(u), H.degree(v)
        # if u_deg - 1 >= n_nodes / 2 and v_deg - 1 >= n_nodes / 2:
        #     if rand.random() < prob:
        #         H.remove_edge(u, v)

    return H


def solve_tsp(graph):
    adj_matrix = nx.adjacency_matrix(graph)
    hamil_path = solve(adj_matrix.todense().tolist())

    path_edges = [(hamil_path[i], hamil_path[i + 1])
                  for i in range(len(hamil_path) - 1)]
    path_edges.append((hamil_path[-1], hamil_path[0]))

    for u, v in graph.edges():
        graph[u][v]["solution"] = int(
            any({u, v}.issubset({src, targ}) for src, targ in path_edges))

    solution_dict = {v: False for v in graph.nodes()}
    for u, v in path_edges:
        solution_dict[u] = True
        solution_dict[v] = True

    nx.set_node_attributes(graph, solution_dict, "solution")

    return graph


def to_one_hot(indices, max_value, axis=-1):
    one_hot = np.eye(max_value)[indices]
    if axis not in (-1, one_hot.ndim):
        one_hot = np.moveaxis(one_hot, -1, axis)

    return one_hot


def graph_to_input_target(graph):
    """Returns 2 graphs with input and target feature vectors for training.
    Args:
    graph: An `nx.Graph` instance.
    Returns:
    The input `nx.Graph` instance.
    The target `nx.Graph` instance.
    Raises:
    ValueError: unknown node type
    """

    def create_feature(attr, fields):
        return np.hstack([np.array(attr[field], dtype=float) for field in fields])

    input_node_fields = ("solution",)
    input_edge_fields = ("weight",)
    target_node_fields = ("solution",)
    target_edge_fields = ("solution",)

    input_graph = graph.copy()
    target_graph = graph.copy()

    solution_length = 0
    for node_index, node_feature in graph.nodes(data=True):
        input_graph.add_node(
            node_index, features=create_feature(node_feature, input_node_fields))
        target_node = to_one_hot(
            create_feature(node_feature, target_node_fields).astype(int), 2)[0]
        target_graph.add_node(node_index, features=target_node)

    for receiver, sender, features in graph.edges(data=True):
        input_graph.add_edge(
            sender, receiver, features=create_feature(features, input_edge_fields))
        target_edge = to_one_hot(
            create_feature(features, target_edge_fields).astype(int), 2)[0]
        target_graph.add_edge(sender, receiver, features=target_edge)
        solution_length += features["weight"] * features["solution"]

    input_graph.graph["features"] = np.array([0.0])
    target_graph.graph["features"] = np.array([solution_length], dtype=float)

    # print(type(input_graph))
    # print(input_graph.graph)
    # print(type(target_graph))
    # print(target_graph.graph)

    return input_graph, target_graph


def generate_networkx_graphs(num_graphs, node_range=(5, 9), prob=0.25, weight_range=(1, 10)):
    """Generate graphs for training.
    Args:
    num_graphs: number of graphs to generate
    num_range: a 2-tuple with the [lower, upper) number of nodes per
      graph
    prob: the probability of removing an edge between any two nodes
    weight_range: a 2-tuple with the [lower, upper) weight to randomly assign
        to (non-removed) edges
    Returns:
    input_graphs: The list of input graphs.
    target_graphs: The list of output graphs.
    graphs: The list of generated graphs.
    """

    input_graphs = []
    target_graphs = []
    graphs = []

    for i in range(num_graphs):
        graph = create_random_graph(node_range, prob, weight_range)
        graph = solve_tsp(graph)
        input_graph, target_graph = graph_to_input_target(graph)
        input_graphs.append(input_graph)
        target_graphs.append(target_graph)
        graphs.append(graph)

    return input_graphs, target_graphs, graphs


#########
# EXPORTS
#########


def create_placeholders(num_graphs):
    input_graphs, target_graphs, _ = generate_networkx_graphs(num_graphs)
    input_ph = utils_tf.placeholders_from_networkxs(input_graphs)
    target_ph = utils_tf.placeholders_from_networkxs(target_graphs)
    return input_ph, target_ph


def make_all_runnable_in_session(*args):
    """Lets an iterable of TF graphs be output from a session as NP graphs."""
    return [utils_tf.make_runnable_in_session(a) for a in args]


def create_feed_dict(num_graphs, input_ph, target_ph):
    """Creates placeholders for the model training and evaluation."""

    inputs, targets, raw_graphs = generate_networkx_graphs(num_graphs)
    input_graphs = utils_np.networkxs_to_graphs_tuple(inputs)
    target_graphs = utils_np.networkxs_to_graphs_tuple(targets)
    feed_dict = {input_ph: input_graphs, target_ph: target_graphs}

    return feed_dict, inputs
