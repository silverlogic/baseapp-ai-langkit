import logging
from typing import Any, Dict, List, Optional, Type

from baseapp_ai_langkit.base.agents.langgraph_agent import LangGraphAgent
from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface
from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema
from baseapp_ai_langkit.runners.models import (
    LLMRunner,
    LLMRunnerNode,
    LLMRunnerNodeUsagePrompt,
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
            return {"nodes": nodes_payload, "edges": edges_payload, "error": None}
    except Exception as e:
        logger.exception("Unexpected error during topology extraction")
        return _error_payload("unknown", str(e))


def _error_payload(code: str, message: str) -> Dict[str, Any]:
    return {"nodes": [], "edges": [], "error": {"code": code, "message": message}}


def _walk_graph(graph: Any, runner_class: Type, runner_record: LLMRunner):
    available_nodes = runner_class.get_available_nodes()
    available_keys = set(available_nodes.keys())

    nodes_payload: List[Dict[str, Any]] = []
    for node_id in _iter_graph_nodes(graph):
        if node_id not in available_keys:
            continue
        node_class = available_nodes[node_id]
        nodes_payload.append(_node_payload(node_id, node_class, runner_record))

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
    key: str, node_class: Type[LLMNodeInterface], runner_record: LLMRunner
) -> Dict[str, Any]:
    return {
        "key": key,
        "class": f"{node_class.__module__}.{node_class.__name__}",
        "kind": _classify_kind(node_class),
        "usage_prompt": _usage_prompt_payload(key, node_class, runner_record),
        "state_modifier": _state_modifier_payload(node_class),
        "model": _model_payload(node_class),
    }


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

    default = _serialize_prompt_schema(schema)
    override = _read_usage_prompt_override(key, runner_record)
    return {"default": default, "override": override}


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


def _state_modifier_payload(
    node_class: Type[LLMNodeInterface],
) -> Optional[Dict[str, Any]]:
    schema = getattr(node_class, "state_modifier_schema", None)
    if not schema:
        return None
    if isinstance(schema, list):
        return {"items": [_serialize_prompt_schema(s) for s in schema]}
    return _serialize_prompt_schema(schema)


def _model_payload(node_class: Type[LLMNodeInterface]) -> Optional[Dict[str, Any]]:
    """Best-effort model metadata. F02 will turn this into an editable surface;
    for S01 the topology endpoint does not yet introspect provider/model_id."""
    return None


def _serialize_prompt_schema(schema: BasePromptSchema) -> Dict[str, Any]:
    return {
        "description": getattr(schema, "description", "") or "",
        "placeholders": list(getattr(schema, "required_placeholders", []) or []),
        "text": getattr(schema, "prompt", "") or "",
    }
