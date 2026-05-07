from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from baseapp_ai_langkit.runners.models import LLMRunner
from baseapp_ai_langkit.runners.topology.extractor import extract_topology


def topology_view(request, pk: int):
    """Admin-scoped JSON endpoint returning a runner's workflow topology.

    Routing concerns are handled by Django admin (`admin_view` for auth + staff
    gate, `get_object_or_404` for unknown pk). Extraction failures never bubble
    up as 5xx — `extract_topology` always returns the structured `{nodes, edges,
    error}` payload, so this view always returns HTTP 200.
    """
    runner_record = get_object_or_404(LLMRunner, pk=pk)
    payload = extract_topology(runner_record)
    return JsonResponse(payload)
