---
name: work-with-prompts
version: 1.0.0
description: Guide for authoring, validating, and overriding LLM prompts in baseapp-ai-langkit via `BasePromptSchema`, the runner registry, and the Django admin. Use this skill when adding a new prompt, changing placeholders on an existing prompt, debugging "missing required placeholder" errors, exposing a prompt to admins, or migrating an inline prompt string into a schema.
triggers:
  - new prompt
  - prompt schema
  - usage_prompt_schema
  - state_modifier_schema
  - placeholder
  - admin prompt
  - LLMRunnerNodeUsagePrompt
  - LLMRunnerNodeStateModifier
  - sync_runners
config:
  package: baseapp_ai_langkit
---

# work-with-prompts

## Purpose

Prompts in `baseapp-ai-langkit` are first-class objects, not inline strings. They flow through three layers:

1. **Code** — `BasePromptSchema` instances declared as class attributes on a node (`LLMNodeInterface` / `LangGraphAgent` / worker).
2. **Database** — `LLMRunner` / `LLMRunnerNode` / `LLMRunnerNodeUsagePrompt` / `LLMRunnerNodeStateModifier` rows store admin-editable overrides.
3. **Admin UI** — non-developers edit prompts at runtime; overrides are validated against the schema's `required_placeholders`.

Using the schema correctly is what makes prompts safe to edit live without breaking placeholders.

---

## The two prompt slots on a node

Every `LLMNodeInterface` exposes:

- **`usage_prompt_schema`** — a single `BasePromptSchema` describing how an *orchestrator* should call into this node. Used by `OrchestratedConversationalWorkflow` to plan node selection.
- **`state_modifier_schema`** — either a single `BasePromptSchema` or a `list[BasePromptSchema]`. Becomes a `SystemMessage` (or list of messages) prepended to the conversation. Used as the node's "system prompt".

Static class attributes:

```python
from langchain_core.messages import AnyMessage
from baseapp_ai_langkit.base.agents.langgraph_agent import LangGraphAgent
from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema


class ProfileAgent(LangGraphAgent):
    usage_prompt_schema = BasePromptSchema(
        description="Hand off to the profile agent when the user asks about account info.",
        prompt="Use the profile_agent when the user mentions: {keywords}.",
        required_placeholders=["{keywords}"],
        placeholders_data={"keywords": "name, email, address"},
    )

    state_modifier_schema = BasePromptSchema(
        description="System prompt for the profile agent.",
        prompt=(
            "You are a profile assistant. The current user is {user_name}. "
            "Only answer questions about their own profile."
        ),
        required_placeholders=["{user_name}"],
    )
```

Placeholder data for `state_modifier_schema` is filled in dynamically at invoke time — `LangGraphAgent.invoke` calls `state_modifier.placeholders_data.update(state)` before formatting. Pass the dynamic values via the workflow's state dict.

---

## How admin overrides work

1. **`@register_runner`** records the runner class.
2. **`python manage.py sync_runners`** walks the registry and `get_or_create`s `LLMRunnerNode` / `LLMRunnerNodeUsagePrompt` / `LLMRunnerNodeStateModifier` rows for every node that has a non-empty `state_modifier_schema`.
3. Admin edits the `usage_prompt` / `state_modifier` text in the admin.
4. On save, `clean_usage_prompt` / `clean_state_modifier` validate that the new text contains all `required_placeholders` — otherwise the save raises `ValidationError`.
5. At runtime, `BaseRunnerInterface.get_dynamic_prompt_schemas(node_key, node_class)` looks up the DB row, calls `get_prompt_schema()` to swap the static template for the override, and threads it back into the node via `instantiate_node`.

If no override exists or it fails validation, the node falls back to the static class-attribute schema. Empty `state_modifier_schema` → no admin row created → no editable prompt for that node.

---

## Authoring rules

1. **Always declare placeholders.** Every `{placeholder}` literal in `prompt` must appear in `required_placeholders` (with the braces, e.g. `"{user_name}"`). `BasePromptSchema.validate` checks substring presence — a missing placeholder won't raise at construction, only at admin-save.
2. **Mark placeholders with curly braces.** `BasePromptSchema.format()` calls `prompt.format(**placeholders_data)`, so tokens must be standard Python `str.format` placeholders.
3. **Keep `description` short.** It's surfaced to the orchestrator (for usage prompts) and to admins. One sentence.
4. **Static schemas are class attributes, not instance attributes.** This is what lets `sync_runners` discover them via `node_class.state_modifier_schema` without instantiating the node. Don't move them into `__init__`.
5. **Lists in `state_modifier_schema`** become multiple system messages. Use a list when you have several distinct system instructions you want admins to be able to edit independently — `sync_runners` indexes them and creates one `LLMRunnerNodeStateModifier` row per index.
6. **Never inline a prompt string in `invoke()` or `tool_func()`.** That bypasses admin overrides and validation. Always go through `BasePromptSchema`.
7. **`conditional_rule`** lets a state modifier be skipped at runtime based on `placeholders_data`. Use it for prompts that only apply in certain contexts (e.g. authenticated users).

---

## Adding a placeholder to an existing prompt

1. Update `prompt` and `required_placeholders` on the schema.
2. Run `docker compose <run> web python manage.py sync_runners`. (This does **not** rewrite admin overrides — they continue to use the prior text.)
3. **Existing admin overrides will fail validation** the next time someone edits them, because they no longer contain the new required placeholder. Two options:
   - **Migration** — write a one-off Django data migration that appends the new placeholder to existing `state_modifier` / `usage_prompt` rows.
   - **Manual cleanup** — coordinate with admins to update each override.
4. Update tests that exercise the schema.

---

## Removing a placeholder

1. Update `prompt` and remove the entry from `required_placeholders`.
2. Run `sync_runners`.
3. Admin overrides keep working (validation only checks that *required* placeholders are present, not that no extras exist). Optional: write a data migration to strip the now-orphaned `{placeholder}` from existing override text.

---

## Debugging

**`ValidationError: The state modifier is not using all required placeholders.`** — admin edited a prompt and dropped a `{placeholder}`. Check `node.state_modifier_schema.required_placeholders` vs the saved text.

**Override doesn't seem to apply at runtime** — confirm `sync_runners` was run after registering the runner, and confirm the node has a non-empty `state_modifier_schema` (empty schemas are skipped during sync). Add logging in `BaseRunnerInterface.get_dynamic_prompt_schemas` to see what's resolved.

**`KeyError` during `format()`** — `placeholders_data` is missing a key declared in `prompt`. For agents, the data is merged from workflow state at invoke time — make sure the workflow puts the expected keys into state.

**Admin row missing** — check that the node's class attribute is *truthy* (not `None` and not an empty `BasePromptSchema`). `sync_runners` skips nodes whose `state_modifier_schema` is falsy.

---

## Tests

For each prompt schema:

- `validate()` returns `True` for the static template.
- `validate(custom_prompt="…")` returns `False` when a required placeholder is missing.
- `format()` returns the expected string when `placeholders_data` is populated.
- `get_langgraph_message(SystemMessage)` returns `None` when `conditional_rule` is set and evaluates to `False`.

Existing reference tests: `baseapp_ai_langkit/base/prompt_schemas/tests/test_base_pormpt_schema.py`.
