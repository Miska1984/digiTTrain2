from django import template

register = template.Library()

@register.filter
def replace_underscore(value: str) -> str:
    """
    Lecseréli az aláhúzásokat szóközre.
    Példa:
        'left_upper_arm' -> 'left upper arm'
    """
    if not isinstance(value, str):
        return value
    return value.replace("_", " ")
