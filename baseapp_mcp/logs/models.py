from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel


class MCPLog(TimeStampedModel):
    tool_name = models.CharField(max_length=255, null=True, blank=True)
    tool_arguments = models.JSONField(null=True, blank=True)
    response = models.JSONField(null=True, blank=True)

    user_identifier = models.CharField(
        max_length=255, null=True, blank=True, help_text="User email, username, or IP address"
    )
    total_tokens = models.IntegerField(null=True, blank=True)
    prompt_tokens = models.IntegerField(null=True, blank=True)
    completion_tokens = models.IntegerField(null=True, blank=True)
    transformer_calls = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _("MCP log")
        verbose_name_plural = _("MCP logs")
