from strands.multiagent.a2a import A2AServer

from samples.a2a_graph_stream.adapter import GraphStreamingAgent

HOST = "127.0.0.1"
PORT = 9000


def main() -> None:
    agent = GraphStreamingAgent()
    server = A2AServer(
        agent=agent,
        host=HOST,
        port=PORT,
        enable_a2a_compliant_streaming=True,
    )
    print(f"Serving A2A graph stream agent on http://{HOST}:{PORT}/", flush=True)
    server.serve()


if __name__ == "__main__":
    main()
