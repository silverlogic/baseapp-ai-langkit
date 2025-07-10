import abc
import json
import logging
import typing
from dataclasses import dataclass
from dataclasses import field as dcfield

import pydash
from django.conf import settings
from django.utils.module_loading import import_string
from rest_framework import status, viewsets
from rest_framework.request import Request
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
            if logger.isEnabledFor(logging.DEBUG):
                try:
                    logger.debug(json.dumps(request.data, indent=4))
                except BaseException as e:
                    logger.error(f"Failed to log request: {e}")

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


@dataclass
class SlackBaseInteractiveEndpointHandler(abc.ABC):
    request: Request
    payload: dict

    # derived properties
    payload_type: str = dcfield(init=False)
    view: dict = dcfield(init=False)
    view_id: int = dcfield(init=False)
    view_hash: str = dcfield(init=False)
    callback_id: str = dcfield(init=False)

    def __post_init__(self, *args, **kwargs):
        self.payload_type = self.payload.get("type")
        self.view = self.payload["view"]
        self.view_id = self.view["id"]
        self.view_hash = self.view["hash"]
        self.callback_id = pydash.get(self.payload, "view.callback_id", "")

    @abc.abstractmethod
    def can_handle(self, **kwargs) -> bool:
        pass

    @abc.abstractmethod
    def handle(self, **kwargs):
        pass


class SlackInteractiveEndpointViewSet(viewsets.ViewSet):
    http_method_names = ["post"]
    permission_classes = [isSlackRequestSigned]

    def create(self, request: Request):
        handler_imports: list[str] = []
        if isinstance(settings.BASEAPP_AI_LANGKIT_SLACK_INTERACTIVE_ENDPOINT_HANDLERS, list):
            handler_imports.extend(settings.BASEAPP_AI_LANGKIT_SLACK_INTERACTIVE_ENDPOINT_HANDLERS)

        try:
            request_data = request.data.copy()
            request_data["payload"] = json.loads(request.data.get("payload"))

            if logger.isEnabledFor(logging.DEBUG):
                try:
                    logger.debug(json.dumps(request_data, indent=4))
                except BaseException as e:
                    logger.error(f"Failed to log request: {e}")

            handler_classes: typing.List[typing.Type[SlackBaseInteractiveEndpointHandler]] = [
                import_string(handler_import) for handler_import in handler_imports
            ]
            handlers = [
                HandlerClass(request=request, payload=request_data["payload"])
                for HandlerClass in handler_classes
            ]

            handled = False
            for handler in handlers:
                if handler.can_handle():
                    try:
                        handler.handle()
                        handled = True
                        break
                    except BaseException as e:
                        logger.error(f"{handler.__class__.__name__} failed to handle request: {e}")
            if not handled:
                raise Exception(f"Failed to handle request {request}")
            return Response(status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error processing Slack webhook: {e}")
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
