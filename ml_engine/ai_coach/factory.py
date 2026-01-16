# ml_engine/ai_coach/factory.py
from .navigator import NavigatorPersona
from .analyst import AnalystPersona

def get_persona(context_app, has_ml_access=False):
    """
    Kiválasztja a megfelelő személyiséget a jogosultság és a helyszín alapján.
    """
    # Ha a felhasználónak van ML_ACCESS-e, minden oldalon az Analyst (Guru) válaszol
    if has_ml_access:
        return AnalystPersona()
    
    # Ha nincs előfizetése, de elemző funkciót próbál használni
    analyst_apps = ['ml_engine', 'diagnostics', 'diagnostics_jobs']
    if context_app in analyst_apps:
        return AnalystPersona()
    
    # Minden egyéb esetben marad a segítőkész Navigator
    return NavigatorPersona()