from langchain.schema import AIMessage

from baseapp_ai_langkit.base.agents.base_agent import DefaultAgent
from baseapp_ai_langkit.base.interfaces.base_runner import BaseRunnerInterface


class ConsoleInterface(BaseRunnerInterface):
    agent: DefaultAgent = None

    def __init__(self, agent):
        self.agent = agent

    def get_user_input(self):
        return input("You: ")

    def display_output(self, output: str | list[str | dict]) -> str:
        print(f"Agent: {output}")

    def run(self) -> str:
        print("Starting chat session. Type 'exit' to quit.")

        while True:
            user_input = self.get_user_input()

            if user_input.lower() in ("exit", "quit"):
                print("Ending chat session.")
                break

            try:
                response = self.agent.invoke(user_input)
                self.display_output(response.content)
            except Exception as e:
                print(f"Error: {str(e)}")
                content = AIMessage(content="An unexpected error occurred. Please try again.")
                self.display_output(content)
