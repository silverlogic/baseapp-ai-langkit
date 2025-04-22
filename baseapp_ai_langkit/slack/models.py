from celery.result import AsyncResult
from django.conf import settings
from django.db import models
from model_utils import Choices
from model_utils.models import TimeStampedModel


class SlackEvent(TimeStampedModel):
    """
    It tracks each slack event request.
    """

    STATUS = Choices(
        ("pending", "Pending"),
        ("running", "Running"),
        ("success", "Success"),
        ("success_with_warnings", "Success with warnings"),
        ("failed", "Failed"),
    )
    data = models.JSONField(null=False, blank=False, default=None)
    status = models.CharField(max_length=10, choices=STATUS, default=STATUS.pending)

    def __str__(self):
        return f"{self.id} - {self.status} - Updated at: {self.updated}"


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
        return f"{self.id} - Celery Task ID: {self.celery_task_id} - Chat session: {self.chat.id} - Slack event: {self.slack_event.id} - Updated at: {self.updated}"

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
