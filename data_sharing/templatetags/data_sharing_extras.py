# /app/data_sharing/templatetags/data_sharing_extras.py

from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    # A kulcsot stringre alakítjuk, mert a JSON/Dict kulcsok gyakran stringként jönnek
    return dictionary.get(str(key))