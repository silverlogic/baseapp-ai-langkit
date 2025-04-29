import logging

from rest_framework import status, viewsets
from rest_framework.response import Response

from baseapp_ai_langkit.slack import tasks
from baseapp_ai_langkit.slack.models import SlackEvent, SlackEventStatus
from baseapp_ai_langkit.slack.permissions import isSlackRequestSigned

logger = logging.getLogger(__name__)


class SlackWebhookViewSet(viewsets.ViewSet):
    http_method_names = ["post"]
    permission_classes = [isSlackRequestSigned]

    def create(self, request):
        try:
            type = request.data["type"]
            if type == "url_verification":
                return Response({"challenge": request.data["challenge"]})
            if type == "event_callback":
                team_id = request.data["team_id"]
                event_ts = request.data["event"]["event_ts"]
                event_type = request.data["event"]["type"]

                self._raise_if_event_exists_and_is_running(team_id, event_ts, event_type)

                slack_event, created = SlackEvent.objects.update_or_create(
                    team_id=team_id,
                    event_ts=event_ts,
                    event_type=event_type,
                    defaults={"data": request.data},
                )
                SlackEventStatus.objects.create(slack_event=slack_event)
                tasks.slack_handle_event_hook_event_callback_data.delay(
                    slack_event_id=slack_event.id
                )
            return Response(status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error processing Slack webhook: {e}")
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _raise_if_event_exists_and_is_running(self, team_id: str, event_ts: str, event_type: str):
        try:
            slack_event = SlackEvent.objects.get(
                team_id=team_id,
                event_ts=event_ts,
                event_type=event_type,
            )
            event_status = slack_event.event_statuses.last()
            if event_status and slack_event.event_statuses.last().status in [
                SlackEventStatus.STATUS.pending,
                SlackEventStatus.STATUS.running,
            ]:
                raise Exception("Event is already running")
        except SlackEvent.DoesNotExist:
            return
