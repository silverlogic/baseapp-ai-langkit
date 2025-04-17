import uuid

import pgtrigger
from django.contrib.auth import get_user_model
from django.db import models
from model_utils import Choices
from model_utils.models import TimeStampedModel

from .managers import ChatSessionManager

User = get_user_model()


class ChatSession(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_sessions")

    objects = ChatSessionManager()

    def __str__(self):
        return f"ChatSession {self.id} for {self.user.email}"

    class Meta:
        get_latest_by = "created"


class ChatMessage(TimeStampedModel):
    ROLE_CHOICES = Choices(("user", "User"), ("assistant", "Assistant"), ("system", "System"))

    session = models.ForeignKey("ChatSession", on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()


class ChatIdentity(TimeStampedModel):
    name = models.CharField(max_length=255)
    avatar = models.ImageField(upload_to="chat-identities", null=True, blank=True)

    chat_intro_title = models.CharField(max_length=255, null=True, blank=True)
    chat_intro_subtitle = models.CharField(max_length=255, null=True, blank=True)
    chat_fab_text = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="The Floating Action Button (FAB) text that will be displayed in the hover state of the Chat FAB.",
    )

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Chat Identities"
        triggers = [
            pgtrigger.Trigger(
                name="ensure_single_active_chat_identity",
                operation=pgtrigger.Update | pgtrigger.Insert,
                when=pgtrigger.Before,
                func="""
                BEGIN
                    IF NEW.is_active THEN
                        UPDATE baseapp_ai_langkit_chats_chatidentity SET is_active = FALSE WHERE id <> NEW.id AND is_active = TRUE;
                    END IF;
                    RETURN NEW;
                END;
                """,
            )
        ]


class ChatPrePromptedQuestion(TimeStampedModel):
    title = models.CharField(
        max_length=255,
        help_text="Title of the pre-prompted question, shown in the dropdown for users to select.",
    )

    prompt = models.TextField(
        max_length=400,
        help_text=(
            "Text shown in the user input when a pre-prompt is selected. "
            "This is the prompt that will be sent to the LLM."
        ),
    )
    order = models.PositiveIntegerField(
        help_text="Order in which the pre-prompted question will be shown in the dropdown from top to bottom.",
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Chat Pre-Prompted Question"
        verbose_name_plural = "Chat Pre-Prompted Questions"
        ordering = ["order"]
