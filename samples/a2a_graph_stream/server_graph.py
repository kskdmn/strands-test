from strands.multiagent import GraphBuilder
from strands.multiagent.graph import Graph

from samples.a2a_graph_stream.nodes import DEFAULT_N, DEFAULT_SLEEP_S, make_counter_node, make_transformer_node


def build_server_graph(*, count: int = DEFAULT_N, sleep_s: float = DEFAULT_SLEEP_S) -> Graph:
    counter = make_counter_node(count=count, sleep_s=sleep_s)
    transformer = make_transformer_node(count=count, sleep_s=sleep_s)

    builder = GraphBuilder()
    builder.add_node(counter, "counter")
    builder.add_node(transformer, "transformer")
    builder.add_edge("counter", "transformer")
    builder.set_entry_point("counter")
    return builder.build()
