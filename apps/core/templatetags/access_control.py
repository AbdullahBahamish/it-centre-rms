from django import template

from apps.core.services import AccessService

register = template.Library()


@register.filter(name="can")
def can(user, action):
    return AccessService.can(user, action)


@register.filter(name="role_name")
def role_name(user):
    return AccessService.get_role_name(user)
