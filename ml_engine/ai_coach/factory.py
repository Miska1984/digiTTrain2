# ml_engine/ai_coach/factory.py
from .navigator import NavigatorPersona
from .analyst import AnalystPersona

def get_persona(context_app, has_ml_access=False):
    """
    Kiválasztja a megfelelő személyiséget a jogosultság alapján.
    
    EGYSZERŰSÍTETT LOGIKA:
    - Van ML előfizetés? → Analyst (Guru mód)
    - Nincs ML előfizetés? → Navigator (Asszisztens mód)
    
    Args:
        context_app: Alkalmazás kontextusa (nem használt már)
        has_ml_access: Van-e aktív ML_ACCESS előfizetés
    
    Returns:
        BasePersona: Navigator vagy Analyst persona
    """
    if has_ml_access:
        # ML előfizetőknek: Guru mód (mélyreható elemzés)
        return AnalystPersona()
    else:
        # Ingyenes felhasználóknak: Asszisztens mód (navigáció + upsell)
        return NavigatorPersona()