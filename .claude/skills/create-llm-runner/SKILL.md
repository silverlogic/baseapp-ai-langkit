---
name: create-llm-runner
version: 1.0.0
description: Guide for adding a new LLM runner (executor or chat) to baseapp-ai-langkit, covering the workflow → node → agent/worker → tool → register_runner chain. Use this skill when the user wants to add a new LLM-driven feature, a new chatbot, a new background LLM pipeline, a new agent, a new worker, a new tool, or any class that ends up wired through `@register_runner`.
triggers:
  - new runner
  - new chat runner
  - new executor
  - new agent
  - new worker
  - new tool
  - new workflow
  - register_runner
  - LangGraphAgent
  - InlineTool
  - ConversationalWorkflow
  - ExecutorWorkflow
  - llm pipeline
  - chatbot
  - llm chain
config:
  package: baseapp_ai_langkit
---

# create-llm-runner

## Purpose

`baseapp-ai-langkit` exposes LLM features through a layered architecture. Adding a new feature almost always means assembling these pieces in order:

```
Tool          → InlineTool subclass with name, description, args_schema, tool_func
Agent/Worker  → LangGraphAgent (with tools) OR a Worker (no tools); both implement LLMNodeInterface
Workflow      → BaseWorkflow / ConversationalWorkflow / OrchestratedConversationalWorkflow / ExecutorWorkflow
Runner        → BaseChatInterface (interactive) or BaseRunnerInterface (one-shot), wires nodes + workflow
@register_runner → makes the runner discoverable and surfaces its prompts in the Django admin
```

For client projects, **do not modify `baseapp_ai_langkit/base/`** — create a new app (e.g. `baseapp_ai_langkit_PROJ`) and mirror the same structure (`base/agents/`, `base/tools/`, `chats/`, `executors/`).

---

## Decision tree

**Is the feature interactive (user sends messages, bot replies, history matters)?**
- Yes → `BaseChatInterface` runner, `ConversationalWorkflow` (or `OrchestratedConversationalWorkflow`).
- No (one-shot generation, batch report, classification) → `BaseRunnerInterface` runner, `ExecutorWorkflow`.

**Does the LLM need to call external APIs / DBs / functions?**
- Yes → use `LangGraphAgent` (or a `LangGraphAgent` subclass that mixes in `AgentsToolsManager`) and define `InlineTool`s.
- No (just generate from a prompt) → use a `Worker` (`MessagesWorker`, `OrchestratorWorker`, `SynthesizerWorker`, or a custom `BaseWorker` subclass).

**Does the runner orchestrate multiple agents/workers?**
- Yes → `OrchestratedConversationalWorkflow` + `ChainOfNodesMixin`.
- No (single node) → `GeneralChatWorkflow` (single-node `ConversationalWorkflow`) or a custom `BaseWorkflow`.

---

## Step-by-step

### 1. Define tools (skip if no external calls)

```python
# baseapp_ai_langkit_PROJ/base/tools/lookup_user_tool.py
from pydantic import BaseModel, Field
from baseapp_ai_langkit.base.tools.inline_tool import InlineTool


class LookupUserArgs(BaseModel):
    user_id: int = Field(description="The user ID to look up")


class LookupUserTool(InlineTool):
    name = "lookup_user"
    description = "Fetch a user's profile by ID"
    args_schema = LookupUserArgs

    def tool_func(self, user_id: int) -> str:
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.get(id=user_id)
        return f"{user.email} ({user.get_full_name()})"
```

`InlineTool.to_langchain_tool()` wraps this into a `StructuredTool` automatically — never construct `StructuredTool` by hand.

### 2. Define the agent (or worker)

```python
# baseapp_ai_langkit_PROJ/base/agents/profile_agent.py
from baseapp_ai_langkit.base.agents.langgraph_agent import LangGraphAgent
from baseapp_ai_langkit_PROJ.base.tools.lookup_user_tool import LookupUserTool


class ProfileAgent(LangGraphAgent):
    tools_list = [LookupUserTool]
```

For tool-less work, subclass an existing worker:

```python
# baseapp_ai_langkit_PROJ/base/workers/summary_worker.py
from baseapp_ai_langkit.base.workers.messages_worker import MessagesWorker


class SummaryWorker(MessagesWorker):
    pass
```

Both must implement `LLMNodeInterface` (already done by parent classes).

### 3. Define / reuse a workflow

Reuse first. Only create a new workflow when you need new state, branches, or a different memory strategy.

```python
# baseapp_ai_langkit_PROJ/base/workflows/profile_chat_workflow.py
from baseapp_ai_langkit.base.workflows.general_chat_workflow import GeneralChatWorkflow


class ProfileChatWorkflow(GeneralChatWorkflow):
    pass
```

### 4. Define the runner

For chats (interactive, has memory):

```python
# baseapp_ai_langkit_PROJ/chats/runners/profile_chat_runner.py
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres import PostgresSaver

from baseapp_ai_langkit.base.interfaces.base_runner import BaseChatInterface
from baseapp_ai_langkit.chats.checkpointer import LangGraphCheckpointer
from baseapp_ai_langkit.runners.registry import register_runner

from baseapp_ai_langkit_PROJ.base.agents.profile_agent import ProfileAgent
from baseapp_ai_langkit_PROJ.base.workflows.profile_chat_workflow import ProfileChatWorkflow


@register_runner
class ProfileChatRunner(BaseChatInterface):
    nodes = {
        "profile_agent": ProfileAgent,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = {"configurable": {"thread_id": str(self.session.id)}}

    def run(self) -> str:
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.checkpointer = self._build_checkpointer()
        self.nodes = self.get_nodes(llm=self.llm, config=self.config)

        workflow = ProfileChatWorkflow(
            llm=self.llm,
            config=self.config,
            checkpointer=self.checkpointer,
            nodes=self.nodes,
        )
        return workflow.execute(self.user_input)["messages"][-1].content

    def _build_checkpointer(self) -> PostgresSaver:
        wrapper = LangGraphCheckpointer()
        wrapper.setup()
        return wrapper.get_checkpointer()
```

For executors (one-shot, no memory):

```python
# baseapp_ai_langkit_PROJ/executors/weekly_report_runner.py
from baseapp_ai_langkit.base.interfaces.base_runner import BaseRunnerInterface
from baseapp_ai_langkit.runners.registry import register_runner


@register_runner
class WeeklyReportRunner(BaseRunnerInterface):
    nodes = {"summarizer": SummaryWorker}

    def run(self) -> str:
        ...
```

### 5. Sync the registry & admin

After adding (or removing) any `@register_runner` class:

```bash
docker compose <run> web python manage.py sync_runners
```

This populates `LLMRunner` / `LLMRunnerNode` / `LLMRunnerNodeUsagePrompt` / `LLMRunnerNodeStateModifier` so admins can edit prompts in the Django admin without redeploying. See `baseapp_ai_langkit/runners/models.py` for the storage model.

### 6. Wire the API surface

- **REST chat** — extend `baseapp_ai_langkit.chats.rest_framework.views` viewsets and override `chat_runner` to point at your new runner.
- **Slack** — for slash commands, register a `ViewSet` in `BASEAPP_AI_LANGKIT_SLACK_SLASH_COMMANDS`. For interactive flows, register a `SlackBaseInteractiveEndpointHandler` subclass in `BASEAPP_AI_LANGKIT_SLACK_INTERACTIVE_ENDPOINT_HANDLERS`. See `testproject` for examples.

### 7. Tests

Required (use the `ensure-test-coverage` skill for the full coverage workflow):
- Tool: `tool_func` happy-path + error path + `to_langchain_tool()` returns a `StructuredTool` with the right name/description.
- Agent: patched `create_agent` (see existing `test_langgraph_agent.py`), verify `tools` list and `invoke()` happy path + error wrap.
- Worker / Workflow: mock the workflow chain and verify execute returns the expected message structure.
- Runner: factory or fixture for `ChatSession`, mock the LLM, assert the run() output.

---

## Rules

1. **Never edit `baseapp_ai_langkit/base/`** for project-specific behavior. Create a new app.
2. **Always `@register_runner`.** A runner that isn't registered won't appear in the admin and won't have editable prompts.
3. **Always run `sync_runners`** after registry changes.
4. **Reuse before extending.** Existing workflows (`GeneralChatWorkflow`, `OrchestratedConversationalWorkflow`, `ExecutorWorkflow`) cover most cases.
5. **Use static prompts via class attributes.** Don't instantiate `BasePromptSchema` per-call — use the `usage_prompt_schema` / `state_modifier_schema` class attributes so admin overrides flow through `runner.get_dynamic_prompt_schemas`. See the `work-with-prompts` skill for details.
6. **Keep tools deterministic.** A tool that does I/O should be mockable in tests via `responses` (HTTP) or by patching the underlying client.
