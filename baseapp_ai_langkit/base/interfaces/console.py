from baseapp_ai_langkit.base.interfaces.base_runner import BaseRunnerInterface
from baseapp_ai_langkit.base.workflows.base_workflow import BaseWorkflow


class ConsoleInterface(BaseRunnerInterface):
    workflow: BaseWorkflow = None

    def __init__(self, workflow: BaseWorkflow):
        self.workflow = workflow

    def get_user_input(self):
        return input("You: ")

    def display_output(self, output: str | list[str | dict]) -> str:
        print(f"LLM: {output}")

    def run(self) -> str:
        print("Starting chat session. Type 'exit' to quit.")

        while True:
            user_input = self.get_user_input()

            if user_input.lower() in ("exit", "quit"):
                print("Ending chat session.")
                break

            try:
                response_content = self._invoke_workflow(user_input)
                self.display_output(response_content)
            except Exception as e:
                print(f"Error: {str(e)}")
                self.display_output("An unexpected error occurred. Please try again.")

    def _invoke_workflow(self, user_input: str) -> str:
        """Invoke a workflow and return the response content."""
        result = self.workflow.execute(user_input)
        # Extract the last message from the workflow result
        messages = result.get("messages", [])
        if not messages:
            return "No response generated."

        last_message = messages[-1]
        # Extract content from the message
        if hasattr(last_message, "content"):
            return last_message.content
        elif isinstance(last_message, dict) and "content" in last_message:
            return last_message["content"]
        else:
            return str(last_message)
