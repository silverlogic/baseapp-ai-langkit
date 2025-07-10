import json
import logging

import pydash
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from baseapp_ai_langkit.slack.permissions import isSlackRequestSigned
from baseapp_ai_langkit.slack.rest_framework.viewsets import (
    SlackBaseInteractiveEndpointHandler,
)
from baseapp_ai_langkit.slack.slack_instance_controller import SlackInstanceController

from ....modals.test_modal import SlackExampleModalBuilder

logger = logging.getLogger(__name__)


class SlackExampleSlashCommandViewSet(viewsets.ViewSet):
    name = "example"
    http_method_names = ["post"]
    permission_classes = [isSlackRequestSigned]

    @csrf_exempt
    def create(self, request: Request):
        try:
            if logger.isEnabledFor(logging.DEBUG):
                try:
                    logger.debug(json.dumps(request.data, indent=4))
                except BaseException as e:
                    logger.error(f"Failed to log request: {e}")

            user_id: str = request.data.get("user_id")
            channel_id: str = request.data.get("channel_id")
            trigger_id: str = request.data.get("trigger_id")

            slack_instance_controller = SlackInstanceController()
            user, _ = slack_instance_controller.get_or_create_user_from_slack_user(
                slack_user_id=user_id
            )

            if user is None:
                return Response(status=status.HTTP_400_BAD_REQUEST)

            modal_builder = SlackExampleModalBuilder(selected_option_1=None, selected_option_2=None)

            slack_instance_controller.slack_web_client.views_open(
                trigger_id=trigger_id, view=modal_builder.build(private_metadata=channel_id)
            ).validate()

            return Response(status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error processing Slack slash command: {e}")
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SlackExampleInteractiveEndpointHandler(SlackBaseInteractiveEndpointHandler):
    def can_handle(self, **kwargs) -> bool:
        if all(
            [
                bool(self.callback_id == SlackExampleModalBuilder.SLACK_VIEW_CALLBACK_ID()),
                bool(self.payload_type in ["block_actions", "view_submission"]),
            ]
        ):
            return True
        return False

    def handle(self, **kwargs):
        slack_instance_controller = SlackInstanceController()

        if self.payload_type == "block_actions":
            state: dict = self.view["state"]
            values: dict = state["values"]
            channel_id: str = self.view["private_metadata"]

            selected_option_1: int | None = None
            selected_option_2: int | None = None

            if selected_option := pydash.get(
                values,
                "{}.static_select.selected_option".format(
                    SlackExampleModalBuilder.SLACK_OPTION_1_BLOCK_ID()
                ),
            ):
                selected_option_1 = int(selected_option["value"])

            if selected_option := pydash.get(
                values,
                "{}.static_select.selected_option".format(
                    SlackExampleModalBuilder.SLACK_OPTION_2_BLOCK_ID()
                ),
            ):
                selected_option_2 = int(selected_option["value"])

            modal_builder = SlackExampleModalBuilder(
                selected_option_1=selected_option_1, selected_option_2=selected_option_2
            )
            slack_instance_controller.slack_web_client.views_update(
                view_id=self.view_id,
                hash=self.view_hash,
                view=modal_builder.build(private_metadata=channel_id),
            )
        elif self.payload_type == "view_submission":
            state: dict = self.view["state"]
            values: dict = state["values"]
            user_id = pydash.get(self.payload, "user.id")
            channel_id: str = self.view["private_metadata"]

            text: str | None = None
            selected_option_1: int | None = None
            selected_option_2: int | None = None

            if selected_option := pydash.get(
                values,
                "{}.action".format(SlackExampleModalBuilder.SLACK_TEXT_BLOCK_ID()),
            ):
                text = selected_option["value"]

            if selected_option := pydash.get(
                values,
                "{}.static_select.selected_option".format(
                    SlackExampleModalBuilder.SLACK_OPTION_1_BLOCK_ID()
                ),
            ):
                selected_option_1 = int(selected_option["value"])

            if selected_option := pydash.get(
                values,
                "{}.static_select.selected_option".format(
                    SlackExampleModalBuilder.SLACK_OPTION_2_BLOCK_ID()
                ),
            ):
                selected_option_2 = int(selected_option["value"])

            slack_instance_controller.slack_web_client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="\n".join(
                    [
                        f"Text :{text or 'null'}",
                        f"Option 1: {str(selected_option_1) or 'null'}",
                        f"Option 2: {str(selected_option_2) or 'null'}",
                    ]
                ),
            )
