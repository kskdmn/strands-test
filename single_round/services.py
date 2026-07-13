from uuid import uuid4

from django.conf import settings
from strands import Agent

from chat.message_parts import build_assistant_parts
from single_round.agents.graph_tools import factory_operations_graph, product_catalog_graph
from single_round.flow_log import FLOW_LOG_HOOKS, log_request_end, log_request_start
from single_round.prompts import build_orchestrator_system_prompt


class SingleRoundService:
    def chat(self, message: str) -> dict[str, str]:
        request_id = uuid4()
        log_request_start(request_id, message)
        try:
            agent = Agent(
                model=settings.CHAT_MODEL_ID,
                name="single_round_orchestrator",
                system_prompt=build_orchestrator_system_prompt(),
                tools=[product_catalog_graph, factory_operations_graph],
                hooks=[FLOW_LOG_HOOKS],
                callback_handler=None,
            )
            result = agent(
                message,
                invocation_state={"request_id": str(request_id)},
            )
            raw_text = str(result)
            thinking_text, final_text = build_assistant_parts(
                agent,
                0,
                result,
                raw_text,
            )
            return {
                "request_id": str(request_id),
                "reply": final_text,
                "thinking": thinking_text,
            }
        finally:
            log_request_end()


single_round_service = SingleRoundService()
