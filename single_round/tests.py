from unittest.mock import MagicMock, patch

from django.test import Client, TestCase

from single_round.agents.graph_runner import format_graph_result
from single_round.prompts import build_orchestrator_system_prompt
from single_round.services import SingleRoundService


class PromptTests(TestCase):
    def test_orchestrator_prompt_mentions_graph_tools(self):
        prompt = build_orchestrator_system_prompt()
        self.assertIn("product_catalog_graph", prompt)
        self.assertIn("factory_operations_graph", prompt)


class GraphRunnerTests(TestCase):
    def test_format_graph_result_uses_last_execution_node(self):
        from types import SimpleNamespace

        agent_result = SimpleNamespace(
            message={"role": "assistant", "content": [{"text": "Final graph answer."}]},
        )
        agent_result.__str__ = lambda self: "Final graph answer."

        last_node = SimpleNamespace(node_id="summarizer")
        node_result = MagicMock()
        node_result.get_agent_results.return_value = [agent_result]

        result = SimpleNamespace(
            status=SimpleNamespace(value="completed"),
            execution_order=[last_node],
            results={"summarizer": node_result},
        )

        self.assertEqual(format_graph_result(result), "Final graph answer.")


class SingleRoundViewTests(TestCase):
    def test_chat_page_renders(self):
        response = Client().get("/single-round/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Single-round chat")
        self.assertContains(response, "single_round/js/single_round.js")


class SingleRoundServiceTests(TestCase):
    def test_chat_returns_reply_without_persisting_messages(self):
        from chat.models import Conversation, Message

        mock_agent = MagicMock()
        mock_agent.messages = [
            {
                "role": "assistant",
                "content": [{"text": "We carry Widget A and Gadget Pro."}],
            },
        ]
        mock_result = MagicMock()
        mock_result.message = {
            "role": "assistant",
            "content": [{"text": "We carry Widget A and Gadget Pro."}],
        }
        mock_result.__str__ = MagicMock(return_value="We carry Widget A and Gadget Pro.")
        mock_agent.return_value = mock_result

        service = SingleRoundService()
        with patch("single_round.services.Agent", return_value=mock_agent):
            result = service.chat("What products do you have?")

        self.assertEqual(result["reply"], "We carry Widget A and Gadget Pro.")
        self.assertIn("request_id", result)
        self.assertEqual(Conversation.objects.count(), 0)
        self.assertEqual(Message.objects.count(), 0)
