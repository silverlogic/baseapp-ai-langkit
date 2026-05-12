"""Admin-scoped JSON endpoints for saving prompt overrides from the F02 graph.

Two per-target POST endpoints back the F02-S01 edit modal:
    * `save_usage_prompt`     → upserts `LLMRunnerNodeUsagePrompt`
    * `save_state_modifier`   → upserts `LLMRunnerNodeStateModifier`

Both apply Django admin's standard staff gate via `admin_site.admin_view(...)`
(wired in `LLMRunnerAdmin.get_urls`) and CSRF protection from Django's default
middleware. Validation goes through the model's `full_clean()` so the legacy
nested-inline editor and the new endpoint share one validation path.

Responses use a stable envelope so the widget can render error UX without
inspecting prose:

    success: 200 {"override": {"text": <str>, "saved_at": <iso8601>}}
    error:   4xx {"error":    {"code": <str>, "message": <str>, "details?": <obj>}}
"""

import json
from typing import Optional, Tuple, Type

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404

from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface
from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema
from baseapp_ai_langkit.runners.models import (
    LLMRunner,
    LLMRunnerNode,
    LLMRunnerNodeStateModifier,
    LLMRunnerNodeUsagePrompt,
    LLMRunnerTopologyLayout,
)


def _json_error(status: int, code: str, message: str, details: Optional[dict] = None) -> JsonResponse:
    body = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return JsonResponse(body, status=status)


def _parse_text(request) -> Tuple[Optional[str], Optional[JsonResponse]]:
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return None, _json_error(400, "validation_error", "Request body must be valid JSON.")
    if not isinstance(payload, dict):
        return None, _json_error(400, "validation_error", "Request body must be a JSON object.")
    text = payload.get("text")
    if not isinstance(text, str):
        return None, _json_error(
            400,
            "validation_error",
            "Field 'text' is required and must be a string.",
        )
    return text, None


def _resolve_node_class(
    pk: int, node_key: str
) -> Tuple[Optional[LLMRunner], Optional[Type[LLMNodeInterface]], Optional[JsonResponse]]:
    """Resolve the runner record + node class without writing anything to the DB.

    Lookup-only by design — node and override rows are created inside the
    `transaction.atomic` block in `_atomic_save`, so a validation failure rolls
    every write back.
    """
    runner = get_object_or_404(LLMRunner, pk=pk)
    try:
        nodes_dict = runner.get_nodes_dict()
    except ValueError as exc:
        return None, None, _json_error(404, "runner_unregistered", str(exc))
    if node_key not in nodes_dict:
        return None, None, _json_error(
            404,
            "node_unknown",
            f"Node '{node_key}' is not declared on runner '{runner.name}'.",
        )
    return runner, nodes_dict[node_key], None


def _validation_error_response(
    error: ValidationError, text: str, schema: BasePromptSchema
) -> JsonResponse:
    """Translate a model-level ValidationError into the structured error envelope.

    `missing_placeholders` is computed explicitly against the schema's
    `required_placeholders` so the UI can list which placeholder is missing,
    regardless of the underlying model's catch-all error message. Matches
    `BasePromptSchema.validate`'s token form: each placeholder must appear
    as `{name}` in the text (not just the bare name).
    """
    missing = [
        ph
        for ph in (getattr(schema, "required_placeholders", []) or [])
        if "{" + ph + "}" not in text
    ]
    if missing:
        return _json_error(
            400,
            "missing_placeholders",
            "The prompt is missing required placeholders: " + ", ".join(missing) + ".",
            details={"missing": missing},
        )
    details = getattr(error, "message_dict", None) or {"messages": list(error.messages)}
    return _json_error(400, "validation_error", "Validation failed.", details=details)


def save_usage_prompt(request, pk: int, node_key: str):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    text, err = _parse_text(request)
    if err is not None:
        return err
    runner, node_class, err = _resolve_node_class(pk, node_key)
    if err is not None:
        return err
    schema = getattr(node_class, "usage_prompt_schema", None)
    if schema is None:
        return _json_error(
            404,
            "prompt_target_unknown",
            f"Node '{node_key}' does not declare a usage_prompt_schema.",
        )
    try:
        with transaction.atomic():
            runner_node, _ = LLMRunnerNode.objects.get_or_create(runner=runner, node=node_key)
            instance, _ = LLMRunnerNodeUsagePrompt.objects.get_or_create(runner_node=runner_node)
            instance.usage_prompt = text
            instance.full_clean()
            instance.save()
            saved_at = instance.modified
    except ValidationError as ve:
        return _validation_error_response(ve, text, schema)
    return JsonResponse(
        {"override": {"text": text, "saved_at": saved_at.isoformat() if saved_at else None}}
    )


def save_state_modifier(request, pk: int, node_key: str, state_modifier_index: int):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    text, err = _parse_text(request)
    if err is not None:
        return err
    runner, node_class, err = _resolve_node_class(pk, node_key)
    if err is not None:
        return err
    state_modifier_list = node_class.get_static_state_modifier_list()
    if state_modifier_index < 0 or state_modifier_index >= len(state_modifier_list):
        return _json_error(
            404,
            "state_modifier_index_out_of_range",
            f"State modifier index {state_modifier_index} is out of range for node "
            f"'{node_key}' (declared count: {len(state_modifier_list)}).",
        )
    schema = state_modifier_list[state_modifier_index]
    try:
        with transaction.atomic():
            runner_node, _ = LLMRunnerNode.objects.get_or_create(runner=runner, node=node_key)
            instance, _ = LLMRunnerNodeStateModifier.objects.get_or_create(
                runner_node=runner_node, index=state_modifier_index
            )
            instance.state_modifier = text
            instance.full_clean()
            instance.save()
            saved_at = instance.modified
    except ValidationError as ve:
        return _validation_error_response(ve, text, schema)
    return JsonResponse(
        {"override": {"text": text, "saved_at": saved_at.isoformat() if saved_at else None}}
    )


# ---------------------------------------------------------------------------
# Topology layout (admin-curated node positions)
# ---------------------------------------------------------------------------


def save_topology_layout(request, pk: int):
    """Persist the per-runner topology layout for the React Flow widget.

    POST body: `{ node_positions: { node_key: { x, y } } }`.
        * Empty `node_positions` clears the layout (admin's "Reset to auto"
          path); the widget then falls back to dagre auto-layout.
        * Non-empty positions overwrite the row wholesale — last save wins.
    Response: `{ layout: { node_positions, saved_at } }` (200).
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    runner = get_object_or_404(LLMRunner, pk=pk)
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return _json_error(400, "validation_error", "Request body must be valid JSON.")
    if not isinstance(body, dict):
        return _json_error(400, "validation_error", "Request body must be a JSON object.")
    raw_positions = body.get("node_positions")
    if not isinstance(raw_positions, dict):
        return _json_error(
            400, "validation_error", "Field 'node_positions' must be a JSON object."
        )

    cleaned: dict = {}
    for key, pos in raw_positions.items():
        if not isinstance(key, str):
            return _json_error(
                400, "validation_error", "node_positions keys must be strings."
            )
        if not isinstance(pos, dict):
            return _json_error(
                400,
                "validation_error",
                f"node_positions['{key}'] must be a JSON object with numeric x and y.",
            )
        x = pos.get("x")
        y = pos.get("y")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return _json_error(
                400,
                "validation_error",
                f"node_positions['{key}'] must have numeric x and y.",
            )
        cleaned[key] = {"x": float(x), "y": float(y)}

    layout, _ = LLMRunnerTopologyLayout.objects.get_or_create(runner=runner)
    layout.node_positions = cleaned
    layout.save()
    return JsonResponse(
        {
            "layout": {
                "node_positions": cleaned,
                "saved_at": layout.modified.isoformat() if layout.modified else None,
            }
        }
    )
