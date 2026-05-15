import logging
from typing import Any, Dict, List, Optional, Type

from baseapp_ai_langkit.base.agents.langgraph_agent import LangGraphAgent
from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface
from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema
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
from baseapp_ai_langkit.runners.topology.extraction_context import (
    topology_extraction_context,
)

logger = logging.getLogger(__name__)


def extract_topology(runner_record: LLMRunner) -> Dict[str, Any]:
    """Introspect a registered runner's compiled LangGraph and return its topology.

    Always returns the structured `{nodes, edges, error}` shape. Never raises;
    extraction failures surface as one of:
        * runner_unregistered           — DB row exists but registry has no class
        * topology_builder_not_declared — runner.workflow_class is None / NotImplementedError
        * workflow_init_failed          — workflow construction raised
        * unknown                       — unexpected exception elsewhere
    """
    try:
        runner_class = runner_record.runner_class
    except ValueError as e:
        return _error_payload("runner_unregistered", str(e))

    try:
        with topology_extraction_context() as ctx:
            try:
                workflow = runner_class.build_topology_workflow(
                    llm=ctx.llm,
                    config=ctx.config,
                    checkpointer=ctx.checkpointer,
                )
            except NotImplementedError as e:
                return _error_payload("topology_builder_not_declared", str(e))
            except Exception as e:
                logger.exception("Workflow init failed during topology extraction")
                return _error_payload("workflow_init_failed", str(e))

            graph = workflow.workflow_chain.get_graph()
            nodes_payload, edges_payload = _walk_graph(graph, runner_class, runner_record)
            return {
                "runner": _build_runner_block(runner_class, runner_record),
                "nodes": nodes_payload,
                "edges": edges_payload,
                "available_models": _available_models_payload(),
                "error": None,
            }
    except Exception as e:
        logger.exception("Unexpected error during topology extraction")
        return _error_payload("unknown", str(e))


def _error_payload(code: str, message: str) -> Dict[str, Any]:
    return {
        "runner": None,
        "nodes": [],
        "edges": [],
        "available_models": [],
        "error": {"code": code, "message": message},
    }


def _resolve_runner_label(runner_class: Type) -> str:
    """Return the runner's display label.

    Uses the runner's declared `label` ClassVar when set, falling back to
    `runner_class.__name__` (class name only, NOT the dotted path stored in
    `LLMRunner.name`). Single source of truth for both the topology payload
    and the admin list view's primary-column accessor.
    """
    declared = getattr(runner_class, "label", None)
    if declared:
        return declared
    return runner_class.__name__


def _build_runner_block(runner_class: Type, runner_record: LLMRunner) -> Dict[str, Any]:
    """Build the topology payload's root `runner` block.

    Carries display identity (`label`, `description`) plus the runner-level
    `default_model` object — same shape as the per-node `model` field, but
    sourced from `LLMRunnerDefaultModelOverride` (one rung above the per-node
    `LLMRunnerNodeModelOverride`). No LLM instantiation, no runner construction,
    no provider SDK loaded.
    """
    default_metadata = getattr(runner_class, "default_model_metadata", None)
    if default_metadata is not None:
        default_initializer_key = default_metadata.initializer_key
        default_model_id = default_metadata.model_id
        default_params = dict(default_metadata.params)
    else:
        default_initializer_key = None
        default_model_id = None
        default_params = {}

    return {
        "label": _resolve_runner_label(runner_class),
        "description": getattr(runner_class, "description", None),
        "default_model": {
            "initializer_key": default_initializer_key,
            "model_id": default_model_id,
            "params": default_params,
            "override": _read_runner_default_override(runner_record),
        },
    }


def _read_runner_default_override(runner_record: LLMRunner) -> Optional[Dict[str, Any]]:
    try:
        override = runner_record.default_model_override
    except LLMRunnerDefaultModelOverride.DoesNotExist:
        return None
    in_catalog = AvailableLLMModel.objects.filter(
        initializer_key=override.initializer_key,
        model_id=override.model_id,
    ).exists()
    saved_at = getattr(override, "modified", None)
    return {
        "initializer_key": override.initializer_key,
        "model_id": override.model_id,
        "params": dict(override.params or {}),
        "saved_at": saved_at.isoformat() if saved_at else None,
        "in_catalog": in_catalog,
    }


def _walk_graph(graph: Any, runner_class: Type, runner_record: LLMRunner):
    available_nodes = runner_class.get_available_nodes()
    available_keys = set(available_nodes.keys())

    nodes_payload: List[Dict[str, Any]] = []
    for node_id in _iter_graph_nodes(graph):
        if node_id not in available_keys:
            continue
        node_class = available_nodes[node_id]
        nodes_payload.append(_node_payload(node_id, node_class, runner_class, runner_record))

    edges_payload: List[Dict[str, Any]] = []
    for edge in _iter_graph_edges(graph):
        source = getattr(edge, "source", None)
        target = getattr(edge, "target", None)
        if source not in available_keys or target not in available_keys:
            continue
        is_conditional = bool(getattr(edge, "conditional", False))
        edges_payload.append(
            {
                "source": source,
                "target": target,
                "kind": "conditional" if is_conditional else "normal",
            }
        )

    return nodes_payload, edges_payload


def _iter_graph_nodes(graph: Any):
    """LangGraph's get_graph().nodes is a dict; yield its keys."""
    nodes = getattr(graph, "nodes", {}) or {}
    if isinstance(nodes, dict):
        return list(nodes.keys())
    return [getattr(n, "id", None) for n in nodes]


def _iter_graph_edges(graph: Any):
    return getattr(graph, "edges", []) or []


def _node_payload(
    key: str,
    node_class: Type[LLMNodeInterface],
    runner_class: Type,
    runner_record: LLMRunner,
) -> Dict[str, Any]:
    return {
        "key": key,
        "class_name": f"{node_class.__module__}.{node_class.__name__}",
        "kind": _classify_kind(node_class),
        "usage_prompt": _usage_prompt_payload(key, node_class, runner_record),
        "state_modifier_prompts": _state_modifier_prompts_payload(key, node_class, runner_record),
        "model": _model_payload(key, runner_class, runner_record),
        "position": _read_persisted_position(key, runner_record),
    }


def _read_persisted_position(key: str, runner_record: LLMRunner) -> Optional[Dict[str, float]]:
    try:
        layout = runner_record.topology_layout
    except LLMRunnerTopologyLayout.DoesNotExist:
        return None
    pos = layout.node_positions.get(key)
    if not isinstance(pos, dict):
        return None
    x = pos.get("x")
    y = pos.get("y")
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    return {"x": float(x), "y": float(y)}


def _classify_kind(node_class: Type[LLMNodeInterface]) -> str:
    """Best-effort classification — agents inherit `LangGraphAgent`, everything
    else under `LLMNodeInterface` is a worker. The `system` kind is intentionally
    not used (system nodes are filtered out, not classified).
    """
    if issubclass(node_class, LangGraphAgent):
        return "agent"
    return "worker"


def _usage_prompt_payload(
    key: str, node_class: Type[LLMNodeInterface], runner_record: LLMRunner
) -> Optional[Dict[str, Any]]:
    schema = getattr(node_class, "usage_prompt_schema", None)
    if not schema:
        return None

    return {
        **_serialize_prompt_schema(schema),
        "override": _read_usage_prompt_override(key, runner_record),
    }


def _read_usage_prompt_override(key: str, runner_record: LLMRunner) -> Optional[Dict[str, Any]]:
    try:
        node_record = runner_record.nodes.get(node=key)
    except LLMRunnerNode.DoesNotExist:
        return None
    try:
        usage_prompt_record = node_record.usage_prompt
    except LLMRunnerNodeUsagePrompt.DoesNotExist:
        return None
    if not usage_prompt_record.usage_prompt:
        return None
    saved_at = getattr(usage_prompt_record, "modified", None)
    return {
        "text": usage_prompt_record.usage_prompt,
        "saved_at": saved_at.isoformat() if saved_at else None,
    }


def _state_modifier_prompts_payload(
    key: str,
    node_class: Type[LLMNodeInterface],
    runner_record: LLMRunner,
) -> List[Dict[str, Any]]:
    schema = getattr(node_class, "state_modifier_schema", None)
    if not schema:
        return []
    schemas = schema if isinstance(schema, list) else [schema]
    return [
        {
            "key": str(idx),
            **_serialize_prompt_schema(s),
            "override": _read_state_modifier_override(key, idx, runner_record),
        }
        for idx, s in enumerate(schemas)
    ]


def _read_state_modifier_override(
    key: str, index: int, runner_record: LLMRunner
) -> Optional[Dict[str, Any]]:
    try:
        node_record = runner_record.nodes.get(node=key)
    except LLMRunnerNode.DoesNotExist:
        return None
    try:
        state_modifier_record = node_record.state_modifiers.get(index=index)
    except LLMRunnerNodeStateModifier.DoesNotExist:
        return None
    if not state_modifier_record.state_modifier:
        return None
    saved_at = getattr(state_modifier_record, "modified", None)
    return {
        "text": state_modifier_record.state_modifier,
        "saved_at": saved_at.isoformat() if saved_at else None,
    }


def _model_payload(key: str, runner_class: Type, runner_record: LLMRunner) -> Dict[str, Any]:
    """Emit per-node model field — defaults from runner's `default_model_metadata`
    classattr; override (if any) from `LLMRunnerNodeModelOverride` + crosscheck against
    `AvailableLLMModel` for `in_catalog`. No initializer is invoked here (the F02-S02
    spec's no-SDK-at-extraction rule)."""
    default_metadata = getattr(runner_class, "default_model_metadata", None)
    if default_metadata is not None:
        default_initializer_key = default_metadata.initializer_key
        default_model_id = default_metadata.model_id
        default_params = dict(default_metadata.params)
    else:
        default_initializer_key = None
        default_model_id = None
        default_params = {}

    return {
        "initializer_key": default_initializer_key,
        "model_id": default_model_id,
        "params": default_params,
        "override": _read_model_override(key, runner_record),
    }


def _read_model_override(key: str, runner_record: LLMRunner) -> Optional[Dict[str, Any]]:
    try:
        node_record = runner_record.nodes.get(node=key)
    except LLMRunnerNode.DoesNotExist:
        return None
    try:
        override = node_record.model_override
    except LLMRunnerNodeModelOverride.DoesNotExist:
        return None
    in_catalog = AvailableLLMModel.objects.filter(
        initializer_key=override.initializer_key,
        model_id=override.model_id,
    ).exists()
    saved_at = getattr(override, "modified", None)
    return {
        "initializer_key": override.initializer_key,
        "model_id": override.model_id,
        "params": dict(override.params or {}),
        "saved_at": saved_at.isoformat() if saved_at else None,
        "in_catalog": in_catalog,
    }


# Preferred display order for the common param names — keeps the modal's
# rendered controls in a stable, predictable order regardless of how the
# catalog row's `default_params` was originally typed (PostgreSQL JSONB
# does not preserve dict insertion order, so we can't rely on what the
# admin wrote in the JSON textarea). Unlisted keys fall through to
# alphabetical at the end.
_PREFERRED_PARAM_ORDER = ("temperature", "top_p", "max_tokens")


def _order_default_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Order `default_params` keys for stable modal rendering: common params
    first (per `_PREFERRED_PARAM_ORDER`), then anything else alphabetically.
    Returns a new dict; does not mutate the input."""
    ordered: Dict[str, Any] = {}
    for k in _PREFERRED_PARAM_ORDER:
        if k in params:
            ordered[k] = params[k]
    for k in sorted(params.keys()):
        if k not in ordered:
            ordered[k] = params[k]
    return ordered


def _available_models_payload() -> List[Dict[str, Any]]:
    """List of catalog rows for the model edit modal. `allowed_params` is derived
    from the catalog row's `default_params.keys()` — admins curate which params
    are tunable by editing the row's JSON. The widget iterates these keys to
    render param controls and reads the value's type to pick the input control.

    Rows are ordered by `label` ASC so the dropdown is alphabetized; param
    keys within each row are ordered for stable display (`_order_default_params`).
    """
    rows: List[Dict[str, Any]] = []
    for row in AvailableLLMModel.objects.all().order_by("label"):
        default_params = _order_default_params(dict(row.default_params or {}))
        rows.append(
            {
                "label": row.label,
                "initializer_key": row.initializer_key,
                "model_id": row.model_id,
                "default_params": default_params,
                "allowed_params": list(default_params.keys()),
            }
        )
    return rows


def _serialize_prompt_schema(schema: BasePromptSchema) -> Dict[str, Any]:
    return {
        "description": getattr(schema, "description", "") or "",
        "required_placeholders": list(getattr(schema, "required_placeholders", []) or []),
        "default_text": getattr(schema, "prompt", "") or "",
    }
