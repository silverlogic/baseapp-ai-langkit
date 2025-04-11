from typing import Any

from django.core.management.base import BaseCommand
from langchain.base_language import BaseLanguageModel
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from baseapp_ai_langkit.base.agents.base_agent import DefaultAgent
from baseapp_ai_langkit.base.interfaces.console import ConsoleInterface
from baseapp_ai_langkit.tools.models import DefaultTool
from baseapp_ai_langkit.vector_stores.models import DefaultVectorStore


class Command(BaseCommand):
    """
    This management command provides a test environment for validating the integration of key components
    in the `baseapp_ai_langkit` application: `DefaultAgent`, `DefaultTool`, and `DefaultVectorStore`.

    Purpose:
    ---------
    In a real-world scenario, the vector store, tools, and agents may be created or initialized
    at different stages depending on the application's requirements:
        - A `VectorStore` might be initialized and populated during a setup phase or as part of a background task.
        - Tools like `DefaultTool` could be dynamically instantiated or configured based on user input
        or contextual application needs.
        - Agents (`DefaultAgent`) may be set up dynamically during runtime with specific LLMs, tools,
        and prompt templates to handle user queries.

    This command simplifies these processes for testing by combining all steps into a single interface,
    allowing you to verify their behavior and interaction.

    Workflow:
    ---------
    1. **Vector Store**:
        - Creates or retrieves a `DefaultVectorStore`.
        - Populates it with sample documents and metadata for testing.

    2. **Tool**:
        - Creates or retrieves a `DefaultTool` linked to the vector store, enabling document retrieval.

    3. **LLM and Prompt Template**:
        - Initializes a language model (`ChatOpenAI`) and sets up a prompt template to guide agent behavior.

    4. **Agent**:
        - Configures a `DefaultAgent` with the LLM, tools, and prompt template.

    5. **Console Interface**:
        - Starts an interactive console (`ConsoleInterface`) to simulate user interactions with the agent.

    6. **Cleanup**:
        - Removes the created vector store and tool to ensure a clean environment after testing.

    Usage:
    ------
    Use this command to verify the `baseapp_ai_langkit` components' interactions in a controlled setup. This approach
    ensures the system components can work together before integrating them into a production workflow.
    """

    help = (
        "Test the DefaultAgent, DefaultTool, and DefaultVectorStore setup via a console interface."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        vector_store = self.create_vector_store()
        tool = self.create_tool(vector_store)
        llm = self.initialize_llm()
        prompt_template = self.create_prompt_template()
        agent = self.create_agent(llm, prompt_template, tool)
        self.run_console_interface(agent)
        self.cleanup(agent, tool, vector_store)

    def create_vector_store(self) -> DefaultVectorStore:
        vector_store, created = DefaultVectorStore.objects.get_or_create(
            name="Test Vector Store", description="A vector store for testing."
        )

        if created:
            self.stdout.write("Vector store created.")

            documents = [
                ("Python is a versatile programming language.", {"category": "programming"}),
                ("The Eiffel Tower is a famous landmark in Paris.", {"category": "landmark"}),
                ("Dogs are loyal companions.", {"category": "animals"}),
            ]

            vector_store.add_documents(documents)
            self.stdout.write(f"Added {len(documents)} documents.")

        return vector_store

    def create_tool(self, vector_store: DefaultVectorStore) -> DefaultTool:
        tool, created = DefaultTool.objects.get_or_create(
            name="Document Search Tool",
            description="A tool for searching documents in the vector store.",
            vector_store=vector_store,
        )

        if created:
            self.stdout.write("Tool created.")

        return tool

    def initialize_llm(self) -> ChatOpenAI:
        llm = ChatOpenAI(temperature=0)
        self.stdout.write("LLM initialized.")
        return llm

    def create_prompt_template(self) -> PromptTemplate:
        prompt_template = PromptTemplate(
            input_variables=["input", "agent_scratchpad"],
            template="""Answer the following question as best you can. You have access to the following tools:

            {tools}

            Use the following format:

            - If the input is a simple greeting or casual conversation, respond directly without using any tools.

            Question: {input}
            Thought: Consider the question and decide if you need to use a tool. If you need a tool, choose exactly one from the following options: {tool_names}
            Action: <the exact tool name from {tool_names}>
            Action Input: <input for the tool>
            Observation: <result of the action>
            ... (Repeat Thought/Action/Action Input/Observation as needed)
            Thought: Once you have enough information, provide the final answer.
            Final Answer: <final answer to the original question>

            {agent_scratchpad}""",
        )
        self.stdout.write("Prompt template ready.")
        return prompt_template

    def create_agent(
        self, llm: BaseLanguageModel, prompt_template: PromptTemplate, tool: DefaultTool
    ) -> DefaultAgent:
        agent = DefaultAgent(
            llm=llm,
            prompt_template=prompt_template,
            tools=[tool.to_langchain_tool()],
        )

        self.stdout.write("Agent initialized.")

        return agent

    def run_console_interface(self, agent: DefaultAgent) -> None:
        console_interface = ConsoleInterface(agent)
        console_interface.run()

    def cleanup(
        self, agent: DefaultAgent, tool: DefaultTool, vector_store: DefaultVectorStore
    ) -> None:
        self.stdout.write("Cleaning up: deleting created objects...")
        tool.delete()
        vector_store.delete()
        self.stdout.write("Cleanup complete.")
