# ml_engine/ai_coach_service.py
from .ai_coach.factory import get_persona
from billing.models import UserSubscription
from .models import DittaMissedQuery  # Importáld az új modellt!
from django.utils import timezone

class DittaCoachService:
    def get_ditta_response(self, user, context_app, user_query=None, history=None, active_role=None):
        """
        Ditta válasz generálása.
        
        Args:
            user: A felhasználó
            context_app: Az alkalmazás kontextusa
            user_query: A felhasználó kérdése
            history: Beszélgetés előzmények (opcionális)
        """
        # 1. Jogosultság ellenőrzése
        has_ml_access = self._check_ml_access(user)
        
        # 2. Persona példányosítása
        persona = get_persona(context_app, has_ml_access)
        
        # 3. Válasz generálása
        response_text = ""
        
        if hasattr(persona, 'get_response'):
            from .ai_coach.analyst import AnalystPersona
            
            if isinstance(persona, AnalystPersona):
                if user_query:
                    # FONTOS: Átadjuk a history-t is!
                    response_text = persona.get_response(
                        user=user,
                        query=user_query,
                        has_ml_access=has_ml_access,
                        history=history,
                        active_role=active_role
                    )
                else:
                    # Kezdő üdvözlés
                    response_text = (
                        f"Szia {user.profile.last_name if user.profile.last_name else user.username}! "
                        "Ditta vagyok, az adat-gurud. 📊 Az ML_ACCESS előfizetésed aktív, "
                        "így készen állok a mélyebb elemzésekre is. Miben segíthetek ma?"
                    )
            else:
                # Navigator (Asszisztens) mód
                response_text = persona.get_response(user, context_app, user_query)
        else:
            response_text = "Szia! Ditta vagyok. Miben segíthetek?"

        # --- Ismeretlen kérések naplózása ---
        if "[MISSED]" in response_text:
            DittaMissedQuery.objects.create(
                user=user,
                query=user_query,
                context_app=context_app
            )
            response_text = response_text.replace("[MISSED]", "").strip()
        
        return response_text

    def _check_ml_access(self, user):
        if not user or not user.is_authenticated:
            return False
            
        return UserSubscription.objects.filter(
            user=user,
            sub_type='ML_ACCESS',
            active=True,
            expiry_date__gt=timezone.now()
        ).exists()