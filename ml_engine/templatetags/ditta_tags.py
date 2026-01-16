# ml_engine/templatetags/ditta_tags.py
from django import template
from ml_engine.ai_coach_service import DittaCoachService
from django.urls import resolve

register = template.Library()
ditta_service = DittaCoachService()

@register.inclusion_tag('ml_engine/components/ditta_widget.html', takes_context=True)
def render_ditta(context):
    request = context['request']
    user = request.user
    
    if not user.is_authenticated:
        return {'show_ditta': False}

    # --- JAVÍTÁS START ---
    # Először megnézzük, hogy a View-ból jött-e egyedi app_context
    app_context = context.get('app_context')

    # Ha a view nem küldött ilyet, akkor marad a régi automatikus app_name felismerés
    if not app_context:
        try:
            match = resolve(request.path)
            app_context = match.app_name
        except:
            app_context = 'unknown'
    # --- JAVÍTÁS END ---

    # Most már a pontos kontextust küldjük a szerviznek (pl. 'create_coach')
    welcome_message = ditta_service.get_ditta_response(user, app_context)

    has_ml_access = ditta_service._check_ml_access(user)

    return {
        'show_ditta': True,
        'welcome_message': welcome_message,
        'app_context': app_context, # Ezt is adjuk vissza a JS-nek
        'has_ml_access': has_ml_access,
        'user': user,
        'csrf_token': context.get('csrf_token') # Biztonság kedvéért
    }