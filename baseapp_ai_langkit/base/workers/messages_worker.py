from typing import List

from langchain_core.messages import AIMessage, AnyMessage

from baseapp_ai_langkit.base.workers.base_worker import BaseWorker


class MessagesWorker(BaseWorker):
    """
    MessagesWorker is a worker that uses a language model to generate responses to user queries.
    It extends the BaseWorker class and implements the invoke method.

    Ideal for workers that need to process a list of messages and return a response.
    """

    def invoke(self, messages: List[AnyMessage], state: dict = {}) -> AIMessage:
        state_modifiers = self.get_state_modifier_list()
        for state_modifier in state_modifiers:
            state_modifier.placeholders_data.update(state)

        state_modifier = self.get_state_modifier_system_message()
        return self.llm.invoke(state_modifier + messages, config=self.config)
