# Baseapp AI Langkit

## Overview

This document provides a comprehensive overview of the architecture and main functionalities of the baseapp-ai-langkit package. It is designed to serve as a quick onboarding guide for new developers.

## Installing in your project

1. **Install the Package**:
    Run the following command to install the `baseapp-ai-langkit` package:
    ```sh
    pip install baseapp-ai-langkit
    ```

2. **Set Up PostgreSQL**:
    Ensure you are using a PostgreSQL image with the pgvector extension activated. For TSL, you can use the following Docker image:
    ```sh
    registry.tsl.io/base/postgres:15.3-pgvector_0.8.0
    ```

3. **Import the package settings**:
    Inside your project's `settings.py` (or `settings/base.py`), import the package's required settings by adding the following line at the top of the file:
    ```python
    from baseapp_ai_langkit.settings import *  # noqa
    ```

4. **Required Environment Variables**:
    The package requires an OpenAI API key to function properly. This key is essential for the default dummy bot and will also be used by any custom bots you create that leverage OpenAI's language models:
    ```sh
    export OPENAI_API_KEY=your_openai_key
    ```

5. **Optional Environment Variables**:
    - **Slack**:
        If you are using the Slack AI Chat integration, you will need the following environment variables:
        ```sh
        export BASEAPP_AI_LANGKIT_SLACK_BOT_USER_OAUTH_TOKEN="xoxb-KEY"
        export SLACK_CLIENT_ID="slack-client-id"
        export SLACK_CLIENT_SECRET="slack-client-secret"
        export SLACK_VERIFICATION_TOKEN="slack-verification-token"
        export SLACK_SIGNING_SECRET="slack-singing-secret"
        ```
        *Note*: For collecting the credentials above, please follow this guide: // TODO: add Slack keys guide.

## Get Started

// TODO: create a get started guide.

## Package Maintenance

This section provides guidance on maintaining the `baseapp-ai-langkit` package.

### Development Environment Setup

1. **Clone the Repository**:
    ```sh
    git clone <repository-url>
    cd baseapp-ai-langkit
    ```

2. **Run docker**:
    You will need to sign in to the TSL harbor account or change the postgres Docker image to another image with the pgvector extension activated.
    ```sh
    docker compose up
    ```

3. **Environment Configuration**:
    Create a `.env` file with the necessary environment variables, including `OPENAI_API_KEY` (if you want to run the dummy bot).

### Testing

Run tests using pytest: `docker compose exec web pytest`

## Architecture

The system is structured into several domains/entities, each responsible for specific functionalities:

- **Agents**: These are the core components that interact with language models to process and respond to user inputs. Agents are equipped with tools that enhance their ability to generate complex responses. They are designed to handle more sophisticated interactions by leveraging these tools.

- **Workers**: Unlike agents, workers are designed for simpler tasks that involve straightforward prompts. They do not utilize tools and are typically used for basic operations within the system.

- **Tools**: These are utilities that agents can leverage to assist in generating responses. They can be managed by the `AgentsToolsManager` and are essential for the advanced capabilities of agents.

- **Vector Stores**: These are used to store and retrieve vector representations of data, facilitating efficient data retrieval and processing.

- **Interfaces**: These define the communication protocols and data exchange formats between different components of the system.

- **Prompt Schemas**: These define the structure and content of prompts used by agents and workers to interact with language models.

## Main Functionalities

### Workflows

Workflows in this system are designed to streamline the interaction between agents and language models. They define the sequence of operations and data transformations required to generate responses to user inputs.

#### Existing Workflows

- **BaseWorkflow**: The foundational class for all workflows, providing a common interface and ensuring necessary methods are implemented.

- **ConversationalWorkflow**: An abstract class extending BaseWorkflow, designed to handle memory and store conversation states, facilitating workflows that require memory management.

- **ExecutorWorkflow**: Executes a list of nodes without maintaining state, suitable for one-time processing tasks (Executors).

- **GeneralChatWorkflow**: A generic example workflow extending ConversationalWorkflow, demonstrating how to create a functional new workflow with memory summarization capabilities.

- **OrchestratedConversationalWorkflow**: Extends ConversationalWorkflow to manage complex interactions by orchestrating multiple nodes (workers and agents), ideal for scenarios requiring node orchestration to respond to user prompts.

### Runners

Runners are responsible for executing workflows and generating automatic records in the admin interface. They manage the lifecycle of workflows, ensuring that all necessary steps are completed and results are recorded.

To register a runner, it is important to use the `@register_runner` decorator from `registry.py`. This decorator not only registers the runner but also ensures that it appears in the admin interface. This allows admin users to edit the prompts directly within the admin panel, providing a convenient way to manage and customize the prompts used by the runners.

Additionally, using the `BaseRunnerInterface` from `base_runner.py` is crucial. This base class defines the structure of the runner and ensures that data from the database is interpreted properly. By adhering to this structure, you can ensure that the runner operates correctly and integrates seamlessly with the rest of the system.

### Executors vs. Chats

- **Executors**: These are designed to be processed once to generate reports or data segments. They do not maintain a state or memory.

- **Chats**: These are focused on user interaction and maintain a memory of past interactions to provide contextually relevant responses.

### REST API for Chats

The system provides a REST API for managing chat sessions. This API allows clients to initiate, update, and terminate chat sessions, as well as retrieve chat histories and agent responses.

The REST API is designed with flexibility in mind, allowing developers to easily extend and customize the behavior of the chat endpoints. This is achieved by using Django Rest Framework's `ViewSet` classes, which can be overridden to modify or extend the default functionality.

#### Customizing ViewSets

To customize the chat behavior, you can extend the provided `ViewSet` classes and override their attributes and methods. This allows you to tailor the chat functionality to meet specific requirements without having to rewrite the entire logic.

For example, you can override the `chat_runner` attribute to use a custom chat runner, or override methods like `list` and `create` to change how chat sessions are listed or created.

Here is an example of how to extend and customize a `ViewSet`:

## Creating Custom Components for Client Projects

In this section, we will guide you through the process of creating custom agents, workers, tools, workflows, and runners for client-specific projects. Each client project should start by creating a separate app, such as `baseapp_ai_langkit_PROJ`, to customize and utilize these functionalities. It is essential to adhere to the architecture provided in the `baseapp_ai_langkit` app. For instance, if you want to create a new agent, it must be placed inside the `base/agents` directory. Following the original structure ensures consistency and compatibility across different components.

### Step-by-Step Guide

1. **Create a Runner**

    - **Location**: Place your runner in the appropriate subapp (`executors` or `chats`).
    - **Purpose**: Decide whether the runner will be an executor (for one-time processing) or a chat (for interactive sessions).
    - **Example**:
        ```python
        from baseapp_ai_langkit.base.interfaces.base_runner import BaseChatInterface

        class CustomChatRunner(BaseChatInterface):
            # Additional configurations
            pass
        ```

2. **Define the Workflow**

    - **Reuse or Extend**: Ideally, reuse existing workflows or extend them to fit the new runner's needs.
    - **Example**:
        ```python
        from baseapp_ai_langkit.base.workflows.orchestrated_conversational_workflow import OrchestratedConversationalWorkflow

        class CustomWorkflow(OrchestratedConversationalWorkflow):
            # Custom logic or extensions
            pass
        ```

3. **Define Nodes for the Runner**

    - **Types**: Nodes can be workflows or agents.
    - **Static Linking**: Link nodes statically in the runner using a unique key for each node.
    - **Example**:
        ```python
        from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface

        class CustomNode(LLMNodeInterface):
            # Implement required methods
            pass
        ```

4. **Create Agents and Tools**

    - **Agents**: If your nodes include agents, create them following the architecture. For using Langgraph workflows, we need Langgraph agents. So use the `LangGraphAgent` base class. Ideally you should also use the `AgentsToolsManager` helper, which simplifies how to select the tools for each agent.
    - **Tools**: Agents require tools, which should be created and managed accordingly.
    - **Example**:
        ```python
        from baseapp_ai_langkit.tools.models import InlineTool

        class CustomTool(InlineTool):
            name = "CustomTool"
            description = "A tool for custom operations."

            def execute(self, *args, **kwargs):
                # Tool logic here
                pass

        from baseapp_ai_langkit.base.agents.langgraph_agent import LangGraphAgent

        class CustomAgent(AgentsToolsManager, LangGraphAgent):
            tools = [CustomTool]

            def __init__(self, *args, **kwargs):
                tools = self.get_tools()
                super().__init__(tools=tools, *args, **kwargs)
        ```

5. **Register the Runner**

    - **Add nodes**: After you have all nodes implemented, add them into the nodes attribute.
    - **Decorator**: Use the `@register_runner` decorator to register the runner.
    - **Admin Customization**: This registration using the decorator allows for prompt customization via the admin interface.
    - **Example**:
        ```python
        @register_runner
        class CustomChatRunner(BaseChatInterface):
            nodes = {
                "custom_agent": CustomAgent,
                "custom_worker": CustomWorker,
            }
            # Runner implementation
        ```

### Example Flow

- **Create a Runner**: Start by creating a runner in the `chats` or `executors` subapp.
- **Define Workflow**: Choose or extend a workflow for the runner.
- **Define Nodes**: Create nodes, which can be workflows or agents, and link them in the runner with unique keys.
- **Create Agents and Tools**: If nodes include agents, create the necessary tools and integrate them.
- **Register the Runner**: Use the `@register_runner` decorator to enable admin customization.

By following this flow, you ensure that all components are properly integrated and customizable, providing a flexible and scalable solution for client-specific needs.


## References

For more detailed information on workflows, workers, agents, and language models, please refer to the [Langchain](https://langchain.com) and [Langgraph](https://langgraph.com) documentation.
