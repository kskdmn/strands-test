import asyncio
import unittest

from samples.a2a_graph_stream.nodes import make_counter_node


class FunctionNodeStreamTests(unittest.TestCase):
    def test_counter_streams_n_data_events_then_result(self):
        node = make_counter_node(count=3, sleep_s=0)

        async def collect():
            data_events = []
            result_events = []
            async for event in node.stream_async("stream demo"):
                if "data" in event:
                    data_events.append(event["data"])
                if "result" in event:
                    result_events.append(event["result"])
            return data_events, result_events

        data_events, result_events = asyncio.run(collect())

        self.assertEqual(data_events, ["counter[0]", "counter[1]", "counter[2]"])
        self.assertEqual(len(result_events), 1)
        self.assertEqual(result_events[0].status.value, "completed")


if __name__ == "__main__":
    unittest.main()
