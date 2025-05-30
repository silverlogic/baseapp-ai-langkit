from celery.result import AsyncResult
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from model_utils import Choices
from model_utils.models import TimeStampedModel

User = get_user_model()


class SlackEvent(TimeStampedModel):
    team_id = models.CharField(max_length=21, null=False, blank=False)
    event_ts = models.CharField(max_length=21, null=False, blank=False)
    event_type = models.CharField(max_length=50, null=False, blank=False)
    data = models.JSONField(null=False, blank=False, default=None)

    def __str__(self):
        return f"{self.id} - Team ID: {self.team_id} - Event TS: {self.event_ts} - Modified at: {self.modified}"

    class Meta:
        unique_together = ("team_id", "event_ts", "event_type")


class SlackEventStatus(TimeStampedModel):
    STATUS = Choices(
        ("pending", "Pending"),
        ("running", "Running"),
        ("success", "Success"),
        ("success_with_warnings", "Success with warnings"),
        ("failed", "Failed"),
    )
    slack_event = models.ForeignKey(
        "baseapp_ai_langkit_slack.SlackEvent",
        related_name="event_statuses",
        null=False,
        blank=False,
        on_delete=models.CASCADE,
    )
    status = models.CharField(max_length=21, choices=STATUS, default=STATUS.pending)
    status_message = models.TextField(null=True, blank=True, default=None)

    def __str__(self):
        return f"{self.id} - Slack event: {self.slack_event.id} - Status: {self.status} - Modified at: {self.modified}"


class SlackAIChat(TimeStampedModel):
    celery_task_id = models.UUIDField(null=True, blank=True)
    chat_session = models.OneToOneField(
        "baseapp_ai_langkit_chats.ChatSession",
        related_name="slack_chat",
        null=False,
        blank=False,
        on_delete=models.CASCADE,
    )
    slack_event = models.OneToOneField(
        "baseapp_ai_langkit_slack.SlackEvent",
        related_name="slack_chat",
        null=False,
        blank=False,
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return f"{self.id} - Celery Task ID: {self.celery_task_id} - Chat session: {self.chat_session.id} - Slack event: {self.slack_event.id} - Modified at: {self.modified}"

    @property
    def is_celery_task_processing(self) -> bool:
        from celery.backends.base import DisabledBackend

        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", True):
            return False
        if not self.celery_task_id:
            return False
        result = AsyncResult(id=self.celery_task_id)
        if isinstance(result.backend, DisabledBackend):
            return False
        return not result.ready()

    class Meta:
        verbose_name = "Slack AI Chat"
        verbose_name_plural = "Slack AI Chats"


class SlackAIChatMessage(TimeStampedModel):
    slack_chat = models.ForeignKey(
        "baseapp_ai_langkit_slack.SlackAIChat",
        related_name="slack_chat_messages",
        null=False,
        blank=False,
        on_delete=models.CASCADE,
    )
    user_message_slack_event = models.ForeignKey(
        "baseapp_ai_langkit_slack.SlackEvent",
        related_name="slack_ai_chat_messages_from_user_message",
        null=False,
        blank=False,
        on_delete=models.CASCADE,
    )
    output_slack_event = models.ForeignKey(
        "baseapp_ai_langkit_slack.SlackEvent",
        related_name="slack_ai_chat_message_from_output_slack_event",
        null=False,
        blank=False,
        on_delete=models.CASCADE,
    )
    output_response_output_data = models.JSONField(null=True, blank=True, default=None)

    def __str__(self):
        return f"{self.id} - Slack chat: {self.slack_chat.id} - User message slack event: {self.user_message_slack_event.id} - Output slack event: {self.output_slack_event.id} - Modified at: {self.modified}"

    class Meta:
        verbose_name = "Slack AI Chat Message"
        verbose_name_plural = "Slack AI Chat Messages"


class SlackAIChatMessageReaction(TimeStampedModel):
    # For now, we are not really restricting the reactions. Once we have the list of all reactions
    # we need, we can add a restriction.
    THUMBS_UP_REACTIONS = ["+1", "thumbsup", "thumbs_up", "vader-thumbsup"]
    THUMBS_DOWN_REACTIONS = ["-1", "thumbsdown", "thumbs_down", "vader-thumbsdown"]

    user = models.ForeignKey(
        User,
        related_name="slack_ai_chat_message_reactions",
        null=False,
        blank=False,
        on_delete=models.CASCADE,
    )
    slack_chat_message = models.ForeignKey(
        "baseapp_ai_langkit_slack.SlackAIChatMessage",
        related_name="reactions",
        null=False,
        blank=False,
        on_delete=models.CASCADE,
    )
    reaction = models.CharField(max_length=64, null=False, blank=False)
    slack_event = models.ForeignKey(
        "baseapp_ai_langkit_slack.SlackEvent",
        related_name="slack_ai_chat_message_reactions",
        null=False,
        blank=False,
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return f"{self.id} - Slack chat message: {self.slack_chat_message.id} - Reaction: {self.reaction} - Modified at: {self.modified}"

    class Meta:
        verbose_name = "Slack AI Chat Message Reaction"
        verbose_name_plural = "Slack AI Chat Message Reactions"
        unique_together = ("user", "slack_chat_message", "reaction")
