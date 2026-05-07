---
name: ensure-test-coverage
version: 1.0.0
description: Ensure every code change in baseapp-ai-langkit ships with passing tests and ≥ 75% coverage before marking a task complete. Always use this skill when implementing a feature, fixing a bug, refactoring, adding a runner/agent/tool/worker/workflow/prompt schema, or about to mark any task done — even if the user doesn't ask for tests explicitly.
triggers:
  - writing new code
  - modifying langkit logic
  - before completing a task
  - implementing a feature
  - fixing a bug
  - refactoring
  - adding a runner
  - adding a tool
  - adding an agent
  - adding a worker
  - adding a workflow
  - adding a prompt schema
config:
  threshold: 75
  service: web
  compose_file: docker-compose.yml
---

# ensure-test-coverage

## Purpose

No task is complete until the test suite passes and coverage is ≥ 75%. The threshold is enforced by `.coveragerc` (`fail_under = 75`). All commands run inside the `web` Docker service — never on the host.

Check container state first: `docker compose ps --status running --services | grep -qx web`
- Running → `docker compose exec web <command>`
- Stopped → `docker compose run --rm web <command>`

(`<run>` below means whichever form applies.)

---

## Workflow

1. Write or update tests alongside the implementation.
2. Run: `docker compose <run> web pytest --cov --cov-report=term-missing`
3. All tests pass and `fail_under` is satisfied → done.
4. Coverage below threshold → read the missing-lines report, add targeted tests, re-run. Repeat.

---

## Commands

```bash
docker compose <run> web pytest --cov --cov-report=term-missing    # recommended
docker compose <run> web pytest --cov --reuse-db                   # faster re-runs
docker compose <run> web pytest baseapp_ai_langkit/<area>/tests/   # scope to one area
```

`.coveragerc` already excludes `./testproject/*` and `**/tests/*` from coverage, so test files don't pollute the score.

---

## Test layout

Tests sit next to the code they cover:

| Code under test | Test directory |
|---|---|
| `baseapp_ai_langkit/base/agents/`     | `baseapp_ai_langkit/base/agents/tests/` |
| `baseapp_ai_langkit/base/tools/`      | `baseapp_ai_langkit/base/tools/tests/` |
| `baseapp_ai_langkit/base/workers/`    | `baseapp_ai_langkit/base/workers/tests/` |
| `baseapp_ai_langkit/base/workflows/`  | `baseapp_ai_langkit/base/workflows/tests/` |
| `baseapp_ai_langkit/base/prompt_schemas/` | `baseapp_ai_langkit/base/prompt_schemas/tests/` |
| `baseapp_ai_langkit/chats/`           | `baseapp_ai_langkit/chats/tests/` |
| `baseapp_ai_langkit/runners/`         | `baseapp_ai_langkit/runners/tests/` |
| `baseapp_ai_langkit/embeddings/`      | `baseapp_ai_langkit/embeddings/tests/` |
| `baseapp_ai_langkit/vector_stores/`   | `baseapp_ai_langkit/vector_stores/tests/` |
| `baseapp_ai_langkit/slack/`           | `baseapp_ai_langkit/slack/tests/` |

Use `factories.py` (factory-boy) for fixtures. Existing factories live alongside tests (e.g. `base/agents/tests/factories.py` provides `LangGraphAgentFactory`, `LLMFactory`).

---

## Rules

1. **Never run on the host.** All pytest and coverage commands run inside the container.
2. **Never mark a task complete if coverage drops below 75%.** `.coveragerc` will fail the run anyway — fix it, don't bypass it.
3. **Mock the LLM, not the framework.** Use `langchain_core.language_models.fake_chat_models.FakeChatModel` (see `base/agents/tests/factories.py`) or `MagicMock`-spec'd nodes (see `base/workflows/tests/test_general_chat_workflow.py`). Don't mock the DB / Django ORM.
4. **Mock external I/O only.** OpenAI HTTP calls, Slack API, Anthropic API, S3 — yes. Postgres / pgvector / langgraph checkpointer — no, run them for real.
5. **Bug fixes → regression test first.** Write a failing test reproducing the bug, then fix it.
6. **Cover both REST and Slack surfaces.** A new chat runner needs tests for the runner *and* its REST viewset (and Slack handler if applicable).
7. **Don't over-test boilerplate.** Skip `__str__`, auto-generated migrations, and trivial property accessors. Focus on runner.run(), workflow execution paths, agent.invoke(), tool functions, prompt schema validate/format.
8. **Tests for `@register_runner` runners must exercise `sync_runners` if the runner introduces new prompt schemas** — otherwise the admin-side state won't match the code.

---

## Common test patterns in this codebase

- **Patch `create_agent`** when testing `LangGraphAgent.invoke` to avoid real LangChain agent construction:
  ```python
  patch("baseapp_ai_langkit.base.agents.langgraph_agent.create_agent")
  ```
- **Use `FakeChatModel`** as the LLM stand-in instead of `ChatOpenAI`.
- **Use `factory.SubFactory(LLMFactory)`** when constructing agent/workflow factories.
- **Stub `workflow_chain`** with a `MagicMock` returning a deterministic `{"messages": [...]}` dict to avoid running the real langgraph state machine.
