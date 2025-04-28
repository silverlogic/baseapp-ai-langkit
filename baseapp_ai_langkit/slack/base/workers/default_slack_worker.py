from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema
from baseapp_ai_langkit.base.workers.messages_worker import MessagesWorker


class DefaultSlackWorker(MessagesWorker):
    state_modifier_schema = BasePromptSchema(
        description="Describe how Slack should respond to the user's message.",
        prompt=(
            "You are a Slack bot that responds to user messages. "
            "\nBelow you have a list of additional information that might be relevant to the user's message."
            "\n{slack_context}"
        ),
        required_placeholders=["slack_context"],
    )

    def __init__(self, slack_context: dict, *args, **kwargs):
        self.slack_context = slack_context
        super().__init__(*args, **kwargs)

    def get_custom_placeholders_data(self) -> dict:
        return {"slack_context": self.slack_context}
