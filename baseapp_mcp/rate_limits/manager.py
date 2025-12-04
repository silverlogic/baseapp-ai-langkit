from django.db import models
from django.utils import timezone


class TokenUsageManager(models.Manager):
    """Custom manager for TokenUsage model."""

    def add_usage(
        self,
        user_identifier: str,
        total_tokens: int = 0,
        transformer_calls: int = 0,
        year: int = None,
        month: int = None,
    ):
        """
        Create a new TokenUsage entry or update existing one by adding tokens.

        Args:
            user_identifier: User email, username, or IP
            total_tokens: Total tokens to add
            transformer_calls: Number of transformer calls to add
            year: Year (defaults to current year)
            month: Month (defaults to current month)

        Returns:
            TokenUsage instance
        """
        now = timezone.now()
        year = year or now.year
        month = month or now.month

        usage, created = self.get_or_create(
            user_identifier=user_identifier,
            year=year,
            month=month,
            defaults={
                "total_tokens": total_tokens,
                "transformer_calls": transformer_calls,
            },
        )

        if not created:
            # Update existing record by adding tokens
            usage.total_tokens += total_tokens
            usage.transformer_calls += transformer_calls
            usage.save(
                update_fields=[
                    "total_tokens",
                    "transformer_calls",
                ]
            )

        return usage

    def get_monthly_usage(self, user_identifier: str, year: int = None, month: int = None):
        """Get token usage for a user in a specific month."""
        now = timezone.now()
        year = year or now.year
        month = month or now.month

        try:
            usage = self.get(
                user_identifier=user_identifier,
                year=year,
                month=month,
            )
            return {
                "total_tokens": usage.total_tokens,
                "transformer_calls": usage.transformer_calls,
            }
        except self.model.DoesNotExist:
            return {
                "total_tokens": 0,
                "transformer_calls": 0,
            }
