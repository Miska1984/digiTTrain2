# diagnostics/templatetags/diagnostics_extras.py
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="create_video_button")
def create_video_button(url):
    """
    🔹 Videó letöltés gombot generál.
    🔹 Biztonságosan ad vissza HTML-t (mark_safe).
    🔹 Üres URL esetén "–" jelet jelenít meg.
    """
    if not url:
        return "–"
    html = f'''
        <a href="{url}" download class="btn btn-sm btn-outline-info">
            <i class="fas fa-download me-1"></i> Letöltés
        </a>
    '''
    return mark_safe(html)
