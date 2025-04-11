from django.db import models
from django.utils.translation import gettext_lazy as _


class ChatSessionManager(models.Manager):
    def get_session_or_error(self, session_id):
        if not session_id:
            raise ValueError(_("session_id is required."))
        try:
            return self.get(id=session_id)
        except self.model.DoesNotExist:
            raise LookupError(_("Session not found."))

    def get_or_create_session(self, session_id, user):
        if session_id:
            try:
                return self.get_session_or_error(session_id)
            except LookupError:
                raise
        else:
            return self.create(user=user)

    def get_or_create_user_session(self, user):
        if user.chat_sessions.exists():
            return user.chat_sessions.latest()
        else:
            return self.create(user=user)
