import json

from django.core.management.base import BaseCommand
from langchain.prompts import PromptTemplate
from langchain.schema import AIMessage
from langchain_openai import ChatOpenAI

from baseapp_ai_langkit.base.agents.langgraph_agent import LangGraphAgent
from baseapp_ai_langkit.tools.models import InMemoryTool
from baseapp_ai_langkit.vector_stores.models import DefaultVectorStore


class Command(BaseCommand):
    """
    This management command demonstrates chaining a custom agent with basic LLM calls
    to generate a comprehensive report based on user input and data insights.

    Workflow:
    ---------
    1. **Vector Store**:
        - Creates or retrieves a `DefaultVectorStore` for raw data.
        - Populates it with example documents representing emotional data over time.

    2. **Tool**:
        - Creates an `InMemoryTool` linked to the vector store for querying raw data.

    3. **Agent**:
        - Configures a `LangGraphAgent` with the tool and a custom prompt to generate insights.

    4. **Prompt and Report Generation**:
        - Takes user input and insights from the agent to create a final report using a secondary prompt.

    Usage:
    ------
    Run the command and optionally provide a message using the --message parameter:
        python manage.py generate_report --message "What are the emotional trends?"
    If no message is provided, the command will prompt you to enter a message interactively.
    """

    help = "Demonstrate chaining of a custom agent and basic LLM calls."

    def add_arguments(self, parser):
        parser.add_argument(
            "--message",
            type=str,
            help="The user input message to generate a report.",
        )

    def handle(self, *args, **options):
        vector_store = self.create_vector_store()
        tool = self.create_tool(vector_store)
        llm = self.initialize_llm()
        agent = self.create_agent(llm, tool)
        user_input = options.get("message") or self.get_user_input()
        insights = self.generate_insights(agent, user_input)
        report = self.generate_report(llm, user_input, insights)

        self.stdout.write(self.style.SUCCESS(f"Final report: {report}"))

    def create_vector_store(self) -> DefaultVectorStore:
        emotions_by_time = {
            "0": {"sad": 17, "happy": 19, "angry": 2, "calm": 62},
            "1": {"sad": 21, "happy": 23, "angry": 54, "calm": 2},
            "2": {"sad": 21, "happy": 23, "angry": 2, "calm": 54},
            "3": {"sad": 19, "happy": 23, "angry": 54, "calm": 4},
            "4": {"sad": 21, "happy": 46, "angry": 6, "calm": 27},
            "5": {"sad": 21, "happy": 50, "angry": 4, "calm": 25},
        }

        vector_store, created = DefaultVectorStore.objects.get_or_create(
            name="Raw Data Vector Store",
            defaults={"description": "A vector store that contains raw data."},
        )

        if created:
            self.stdout.write(self.style.SUCCESS("Vector store created."))
            vector_store.add_documents(
                [(json.dumps(emotions_by_time), {"category": "emotions_by_time"})]
            )
            self.stdout.write("Added emotional data to vector store.")

        return vector_store

    def create_tool(self, vector_store: DefaultVectorStore) -> InMemoryTool:
        raw_data_tool = InMemoryTool(
            vector_store=vector_store,
            name="raw_data_tool",
            description="A tool that provides access to raw data.",
        )

        return raw_data_tool

    def initialize_llm(self) -> ChatOpenAI:
        llm = ChatOpenAI(temperature=0)
        self.stdout.write(self.style.SUCCESS("LLM initialized."))
        return llm

    def create_agent(self, llm: ChatOpenAI, tool: InMemoryTool) -> LangGraphAgent:
        prompt = f"""
            You are an Agent that generates mathematical insights that should be useful to answer the user's question.

            You have access to the following tool: {tool.name} - {tool.description}
        """

        agent = LangGraphAgent(
            tools=[tool.to_langchain_tool()], llm=llm, prompt_template=prompt, debug=True
        )

        self.stdout.write(self.style.SUCCESS("Insights agent initialized."))
        return agent

    def get_user_input(self) -> str:
        return input("Enter a question: ")

    def generate_insights(self, agent: LangGraphAgent, user_input: str) -> str:
        try:
            insights = agent.invoke(user_input).content
            self.stdout.write(self.style.SUCCESS("Generated insights"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            insights = AIMessage(content="An unexpected error occurred. Please try again.")
        return insights

    def generate_report(self, llm: ChatOpenAI, user_input: str, insights: str) -> str:
        prompt_template = PromptTemplate(
            input_variables=["user_input", "insights"],
            template="""
                You're an AI that generates comprehensive reports based on insights and user input.

                Use the following insights: {insights}

                To generate a report responding directly to the user input: {user_input}

                Act as if you generated the insights yourself, don't use expressions such as
                "based on the provided data" or "according to the insights".
            """,
        )
        final_prompt = prompt_template.format(user_input=user_input, insights=insights)
        response = llm.invoke(final_prompt)
        return response.content
