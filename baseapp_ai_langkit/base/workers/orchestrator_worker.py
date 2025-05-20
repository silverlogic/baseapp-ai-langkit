from typing import List, Tuple

from langchain_core.messages import AnyMessage
from pydantic import BaseModel, Field

from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema
from baseapp_ai_langkit.base.workers.messages_worker import MessagesWorker


class AvailableNode(BaseModel):
    name: str = Field(description="Unique identifier or name of the selected agent/worker.")
    prompt: str = Field(
        description=(
            "The input prompt that will be sent to the selected worker/agent."
            "Ensure clarity and conciseness, avoiding requests for overly long responses."
            "Provide enough context for an accurate response while keeping the request specific and actionable."
        ),
    )


class OrchestratorResponse(BaseModel):
    nodes: List[AvailableNode] = Field(
        description=(
            "A list of workers/agents that will be used to process and respond to the user's prompt."
            " Each worker/agent is capable of contributing to the response."
        ),
    )
    synthesizer_context: str = Field(
        description=(
            "Write a context that will help the synthesizer to answer the user prompt."
            "\nWrite the context based on what the user asked. Remember that the synthesizer don't have access to the memory of the conversation."
        ),
    )


class OrchestratorWorker(MessagesWorker):
    """
    OrchestratorWorker is a worker designed to orchestrate workers and agents to answer the user prompt.
    Use this worker as basis for creating new orchestrators or just reuse it.

    Args:
        available_nodes_list (List[Tuple[str, str]]): A list of available nodes with their description.
    """

    state_modifier_schema = BasePromptSchema(
        description=(
            "Prompt schema for the orchestrator worker. It must guide the orchestrator to select the agents and workers and create the synthesizer context."
        ),
        prompt=(
            "\nYou are an orchestrator. Your role is to manage the conversation, ensuring the best response for the user."
            "\nAlways respond only to the latest `HumanMessage` in the messages list."
            "\nYour responsibility is to select the most relevant agents and workers to process the user prompt."
            "\nIf no available agent or worker is suitable, return an empty list (`[]`)."
            "\nHere are the available agents and workers:"
            "\n{available_nodes_list}"
            "\n### Available Context"
            "\n- If you can confidently answer the user prompt without selecting any agent/worker, do so. Otherwise, ensure that the most relevant agents/workers are selected."
            "\n### Your Tasks"
            "\n1. Identify the required agents/workers based on the user prompt."
            "\n2. Create specific prompts for each selected agent/worker."
            "\n3. Provide a synthesized context with all relevant information to help generate the best response."
            "\nBe precise, leverage all available resources, and ensure clarity in the orchestration process."
        ),
        required_placeholders=["available_nodes_list"],
    )

    def __init__(
        self,
        available_nodes_list: List[Tuple[str, str]],
        *args,
        **kwargs,
    ):
        self.available_nodes_list = available_nodes_list
        super().__init__(*args, **kwargs)
        # TODO: Move this to a function, so it can get overridden if needed.
        self.llm = self.llm.with_structured_output(OrchestratorResponse)

    def get_custom_placeholders_data(self) -> dict:
        return self.get_state_modifier_placeholders(self.available_nodes_list)

    def get_state_modifier_placeholders(
        self,
        available_nodes_list: List[Tuple[str, str]],
    ) -> dict:
        return {
            "available_nodes_list": "\n".join(
                [
                    f"> Worker/Agent name: {node[0]} - How to use it: {node[1]}"
                    for node in available_nodes_list
                ]
            )
        }

    def invoke(self, messages: List[AnyMessage]) -> OrchestratorResponse:
        return super().invoke(messages)
