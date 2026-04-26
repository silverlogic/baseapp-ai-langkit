from __future__ import annotations

import typing as typ

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

from baseapp_mcp.permissions.models import MCP_TOOL_PERMISSION_GROUPS

User = get_user_model()

if typ.TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser


def create_mcp_permission_groups(sender, **kwargs):
    from django.contrib.auth.models import Group, Permission
    from django.contrib.contenttypes.models import ContentType

    try:
        ct, _ = ContentType.objects.get_or_create(
            app_label="baseapp_mcp_permissions",
            model="mcptoolpermission",
        )
        for group_name, codename, permission_name in MCP_TOOL_PERMISSION_GROUPS:
            permission, _ = Permission.objects.get_or_create(
                codename=codename,
                content_type=ct,
                defaults={"name": permission_name},
            )
            group, _ = Group.objects.get_or_create(name=group_name)
            group.permissions.add(permission)

        standard_group = Group.objects.get(name=MCP_TOOL_PERMISSION_GROUPS[0][0])
        for user in get_user_model().objects.all():
            user.groups.add(standard_group)
    except Exception:
        pass


@receiver(
    post_save, sender=User, dispatch_uid="baseapp_mcp.permissions.signals.assign_default_mcp_group"
)
def assign_default_mcp_group(sender, instance: AbstractBaseUser, created: bool, **_kwargs):
    if created:
        if group := Group.objects.filter(name=MCP_TOOL_PERMISSION_GROUPS[0][0]).first():
            instance.groups.add(group)
