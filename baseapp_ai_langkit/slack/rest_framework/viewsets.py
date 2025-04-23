import json
import logging

from rest_framework import status, viewsets
from rest_framework.response import Response

from baseapp_ai_langkit.slack import tasks
from baseapp_ai_langkit.slack.models import SlackEvent
from baseapp_ai_langkit.slack.permissions import isSlackRequestSigned

logger = logging.getLogger(__name__)


class SlackWebhookViewSet(viewsets.ViewSet):
    # TODO: allow only POST request.
    permission_classes = [isSlackRequestSigned]

    def create(self, request):
        try:
            type = request.data["type"]
            if type == "url_verification":
                return Response({"challenge": request.data["challenge"]})
            if type == "event_callback":
                data = json.loads(request.body.decode("utf-8"))
                slack_event = SlackEvent.objects.create(data=data)
                tasks.slack_handle_event_hook_event_callback_data.delay(
                    slack_event_id=slack_event.id
                )
            return Response(status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error processing Slack webhook: {e}")
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
