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
from typing import Any, Dict, List, Optional, Tuple, Type

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404

from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface
from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema
from baseapp_ai_langkit.runners.model_initializers.registry import (
    LLMModelInitializerRegistry,
)
from baseapp_ai_langkit.runners.models import (
    AvailableLLMModel,
    LLMRunner,
    LLMRunnerDefaultModelOverride,
    LLMRunnerNode,
    LLMRunnerNodeModelOverride,
    LLMRunnerNodeStateModifier,
    LLMRunnerNodeUsagePrompt,
    LLMRunnerTopologyLayout,
)

# Param validation ranges (global for v1; per-provider quirks surface at runtime).
_TEMPERATURE_RANGE = (0.0, 1.0)
_TOP_P_RANGE = (0.0, 1.0)


def _json_error(
    status: int, code: str, message: str, details: Optional[dict] = None
) -> JsonResponse:
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
        return (
            None,
            None,
            _json_error(
                404,
                "node_unknown",
                f"Node '{node_key}' is not declared on runner '{runner.name}'.",
            ),
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
        return _json_error(400, "validation_error", "Field 'node_positions' must be a JSON object.")

    cleaned: dict = {}
    for key, pos in raw_positions.items():
        if not isinstance(key, str):
            return _json_error(400, "validation_error", "node_positions keys must be strings.")
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


# ---------------------------------------------------------------------------
# Model override (F02-S02)
# ---------------------------------------------------------------------------


def _validate_param_values(params: Dict[str, Any], allowed_params: List[str]) -> List[str]:
    """Return a list of param keys whose values are out-of-range or wrong-typed.

    Globals (not per-initializer) for v1:
        temperature  → float in [0.0, 2.0]
        top_p        → float in [0.0, 1.0]
        max_tokens   → positive int
    """
    invalid: List[str] = []
    for key, value in params.items():
        if key not in allowed_params:
            continue  # already covered by `param_not_allowed`
        if key == "temperature":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                invalid.append(key)
                continue
            if not (_TEMPERATURE_RANGE[0] <= value <= _TEMPERATURE_RANGE[1]):
                invalid.append(key)
        elif key == "top_p":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                invalid.append(key)
                continue
            if not (_TOP_P_RANGE[0] <= value <= _TOP_P_RANGE[1]):
                invalid.append(key)
        elif key == "max_tokens":
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                invalid.append(key)
    return invalid


def save_model_override(request, pk: int, node_key: str):
    if request.method == "DELETE":
        return _reset_model_override(request, pk, node_key)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST", "DELETE"])
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return _json_error(400, "validation_error", "Request body must be valid JSON.")
    if not isinstance(payload, dict):
        return _json_error(400, "validation_error", "Request body must be a JSON object.")

    initializer_key = payload.get("initializer_key")
    model_id = payload.get("model_id")
    params = payload.get("params", {})
    if not isinstance(initializer_key, str) or not initializer_key:
        return _json_error(
            400,
            "validation_error",
            "Field 'initializer_key' is required and must be a non-empty string.",
        )
    if not isinstance(model_id, str) or not model_id:
        return _json_error(
            400,
            "validation_error",
            "Field 'model_id' is required and must be a non-empty string.",
        )
    if not isinstance(params, dict):
        return _json_error(400, "validation_error", "Field 'params' must be a JSON object.")

    runner, _node_class, err = _resolve_node_class(pk, node_key)
    if err is not None:
        return err

    initializer = LLMModelInitializerRegistry.get(initializer_key)
    if initializer is None:
        return _json_error(
            400,
            "initializer_unknown",
            f"Initializer '{initializer_key}' is not registered.",
        )

    catalog_row = AvailableLLMModel.objects.filter(
        initializer_key=initializer_key, model_id=model_id
    ).first()
    if catalog_row is None:
        return _json_error(
            400,
            "model_not_in_catalog",
            f"Model {initializer_key}:{model_id} is not in the AvailableLLMModel catalog.",
        )

    # The catalog row's `default_params` keys define which params admins can
    # tune for this model. Anything outside that set is rejected — keeps the
    # modal's UI and the save endpoint coherent.
    allowed_params = list((catalog_row.default_params or {}).keys())
    disallowed = [k for k in params.keys() if k not in allowed_params]
    if disallowed:
        return _json_error(
            400,
            "param_not_allowed",
            (
                f"Params {disallowed} are not in the catalog row's default_params for "
                f"{initializer_key}:{model_id} (allowed: {allowed_params})."
            ),
            details={"disallowed": disallowed},
        )

    invalid = _validate_param_values(params, allowed_params)
    if invalid:
        return _json_error(
            400,
            "param_invalid",
            f"Params {invalid} are out of range or wrong-typed.",
            details={"invalid": invalid},
        )

    with transaction.atomic():
        runner_node, _ = LLMRunnerNode.objects.get_or_create(runner=runner, node=node_key)
        override, _ = LLMRunnerNodeModelOverride.objects.update_or_create(
            runner_node=runner_node,
            defaults={
                "initializer_key": initializer_key,
                "model_id": model_id,
                "params": params,
            },
        )
        saved_at = override.modified

    return JsonResponse(
        {
            "override": {
                "initializer_key": initializer_key,
                "model_id": model_id,
                "params": params,
                "saved_at": saved_at.isoformat() if saved_at else None,
                "in_catalog": True,
            }
        }
    )


def _reset_model_override(request, pk: int, node_key: str):
    """DELETE handler: drop the per-node override and fall back to the runner default.

    Idempotent — if no override exists the request still returns 200 with
    `{override: null}`. Mirrors the F02-S01 layout reset semantics.
    """
    runner, _node_class, err = _resolve_node_class(pk, node_key)
    if err is not None:
        return err
    LLMRunnerNodeModelOverride.objects.filter(
        runner_node__runner=runner, runner_node__node=node_key
    ).delete()
    return JsonResponse({"override": None})


# ---------------------------------------------------------------------------
# Runner-level default model override (F03-S01)
# ---------------------------------------------------------------------------


def _resolve_runner(pk: int) -> Tuple[Optional[LLMRunner], Optional[JsonResponse]]:
    """Resolve the runner record for runner-level endpoints. Mirrors `_resolve_node_class`
    but without the per-node resolution — runner-level rows are scoped to the runner only.
    """
    runner = get_object_or_404(LLMRunner, pk=pk)
    try:
        runner.get_nodes_dict()  # forces the class lookup; raises ValueError when orphan
    except ValueError as exc:
        return None, _json_error(404, "runner_unregistered", str(exc))
    return runner, None


def save_runner_default_model(request, pk: int):
    """POST/DELETE handler for the runner-level default-model override.

    POST   — upsert `LLMRunnerDefaultModelOverride` for the runner.
    DELETE — drop the row idempotently (200 even when no row exists).

    Mirrors `save_model_override` one rung higher: same staff gate (via
    `admin_site.admin_view`), same CSRF, same structured error envelope, same
    error codes (`validation_error`, `initializer_unknown`, `model_not_in_catalog`,
    `param_not_allowed`, `param_invalid`, `runner_unregistered`). No `node_key`.
    """
    if request.method == "DELETE":
        return _reset_runner_default_model(request, pk)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST", "DELETE"])
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return _json_error(400, "validation_error", "Request body must be valid JSON.")
    if not isinstance(payload, dict):
        return _json_error(400, "validation_error", "Request body must be a JSON object.")

    initializer_key = payload.get("initializer_key")
    model_id = payload.get("model_id")
    params = payload.get("params", {})
    if not isinstance(initializer_key, str) or not initializer_key:
        return _json_error(
            400,
            "validation_error",
            "Field 'initializer_key' is required and must be a non-empty string.",
        )
    if not isinstance(model_id, str) or not model_id:
        return _json_error(
            400,
            "validation_error",
            "Field 'model_id' is required and must be a non-empty string.",
        )
    if not isinstance(params, dict):
        return _json_error(400, "validation_error", "Field 'params' must be a JSON object.")

    runner, err = _resolve_runner(pk)
    if err is not None:
        return err

    initializer = LLMModelInitializerRegistry.get(initializer_key)
    if initializer is None:
        return _json_error(
            400,
            "initializer_unknown",
            f"Initializer '{initializer_key}' is not registered.",
        )

    catalog_row = AvailableLLMModel.objects.filter(
        initializer_key=initializer_key, model_id=model_id
    ).first()
    if catalog_row is None:
        return _json_error(
            400,
            "model_not_in_catalog",
            f"Model {initializer_key}:{model_id} is not in the AvailableLLMModel catalog.",
        )

    allowed_params = list((catalog_row.default_params or {}).keys())
    disallowed = [k for k in params.keys() if k not in allowed_params]
    if disallowed:
        return _json_error(
            400,
            "param_not_allowed",
            (
                f"Params {disallowed} are not in the catalog row's default_params for "
                f"{initializer_key}:{model_id} (allowed: {allowed_params})."
            ),
            details={"disallowed": disallowed},
        )

    invalid = _validate_param_values(params, allowed_params)
    if invalid:
        return _json_error(
            400,
            "param_invalid",
            f"Params {invalid} are out of range or wrong-typed.",
            details={"invalid": invalid},
        )

    with transaction.atomic():
        override, _ = LLMRunnerDefaultModelOverride.objects.update_or_create(
            runner=runner,
            defaults={
                "initializer_key": initializer_key,
                "model_id": model_id,
                "params": params,
            },
        )
        saved_at = override.modified

    return JsonResponse(
        {
            "override": {
                "initializer_key": initializer_key,
                "model_id": model_id,
                "params": params,
                "saved_at": saved_at.isoformat() if saved_at else None,
                "in_catalog": True,
            }
        }
    )


def _reset_runner_default_model(request, pk: int):
    """DELETE handler for the runner-level override.

    Idempotent — when no row exists, still returns 200 with `{override: null}`.
    """
    runner, err = _resolve_runner(pk)
    if err is not None:
        return err
    LLMRunnerDefaultModelOverride.objects.filter(runner=runner).delete()
    return JsonResponse({"override": None})
