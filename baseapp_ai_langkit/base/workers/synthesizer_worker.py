from typing import List

from langchain_core.messages import AIMessage, AnyMessage

from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema
from baseapp_ai_langkit.base.workers.messages_worker import MessagesWorker


class SynthesizerWorker(MessagesWorker):
    """
    SynthesizerWorker is a worker designed to synthesize the final response from the agents and workers.
    Use this worker as basis for creating new synthesizers or just reuse it.

    Make use to send all required placeholders within the conversation state.
    """

    state_modifier_schema = [
        BasePromptSchema(
            description=(
                "Main instruction for the synthesizer worker. It must guide the synthesizer to generate the final response."
            ),
            prompt=(
                "You are an synthesizer agent. Your responsibility is consolidate the final answer based on what the agents and workers provided."
                "\n**The user prompt that you must answer:** {user_prompt}"
                "\nIf you need any more context to answer the user, you can use the context the orchestrator wrote to you: {synthesizer_context}"
            ),
            required_placeholders=["user_prompt", "synthesizer_context"],
        ),
        BasePromptSchema(
            description=(
                "When workers/agents are used to answer the user prompt, the prompt must list them to give context to the synthesizer."
            ),
            prompt=(
                "These are all the agents and workers used in this conversation:"
                "\n{selected_nodes_list}"
                "\nBelow you can find all the answers of the agents/workers used to answer the last user prompt."
                "\nYour answer must not mention the used agents/workers."
            ),
            required_placeholders=["selected_nodes_list"],
            conditional_rule=lambda state: len(state.get("selected_nodes_list") or []) > 0,
        ),
    ]

    def invoke(self, messages: List[AnyMessage], state: dict) -> AIMessage:
        state_modifiers = self.get_state_modifier_list()
        for state_modifier in state_modifiers:
            state_modifier.placeholders_data = {**state_modifier.placeholders_data, **state}

        state_modifier = self.get_state_modifier_system_message()
        return self.llm.invoke(state_modifier + messages, config=self.config)
