# /app/data_sharing/templatetags/data_sharing_extras.py

from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Lehetővé teszi szótár elemeinek elérését kulcs alapján a Django sablonban.
    Használata: {{ dictionary|get_item:key }}
    """
    return dictionary.get(key)