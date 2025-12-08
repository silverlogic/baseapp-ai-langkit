from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel

from .manager import TokenUsageManager


class BaseTokenUsage(TimeStampedModel):
    """
    Base abstract model for tracking token usage per user per month.
    """

    user_identifier = models.CharField(
        max_length=255, db_index=True, help_text="User email, username, or IP address"
    )
    year = models.IntegerField(db_index=True, help_text="Year of usage")
    month = models.IntegerField(db_index=True, help_text="Month of usage (1-12)")

    total_tokens = models.IntegerField(default=0)
    transformer_calls = models.IntegerField(default=0)

    # Custom manager for updating and retrieving monthly usage of a user
    objects = TokenUsageManager()

    class Meta:
        abstract = True
        verbose_name = _("Token usage")
        verbose_name_plural = _("Token usages")
        ordering = ["-year", "-month", "user_identifier"]
        unique_together = [["user_identifier", "year", "month"]]

    def __str__(self):
        return f"{self.user_identifier} - {self.year}/{self.month} - {self.total_tokens} tokens - {self.transformer_calls} calls"


class TokenUsage(BaseTokenUsage):
    class Meta(BaseTokenUsage.Meta):
        pass
