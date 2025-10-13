# users/templatetags/user_extras.py
from django import template
from users.utils import _check_user_role

register = template.Library()


@register.filter
def has_role(user, role_name):
    """
    Ellenőrzi, hogy a felhasználónak van-e egy adott szerepköre.
    Használat:
        {% if request.user|has_role:"Sportoló" %}
    """
    try:
        return _check_user_role(user, role_name)
    except Exception:
        return False


@register.filter
def has_any_role(user, roles):
    """
    Ellenőrzi, hogy a felhasználónak van-e legalább az egyik megadott szerepköre.
    Több szerep vesszővel elválasztva adható meg.
    Használat:
        {% if request.user|has_any_role:"Sportoló,Edző,Egyesületi vezető" %}
    """
    try:
        role_list = [r.strip() for r in roles.split(",")]
        return any(_check_user_role(user, role) for role in role_list)
    except Exception:
        return False
