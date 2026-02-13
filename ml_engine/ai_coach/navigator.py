# ml_engine/ai_coach/navigator.py
from .base_persona import BasePersona
from django.urls import reverse
from datetime import date
from .ui_knowledge import UI_NAVIGATION_MAP
from ml_engine.models import DittaMissedQuery

class NavigatorPersona(BasePersona):
    """
    Navigator (Asszisztens) mód - INGYENES
    - Intelligens válaszadás a [MISSED] helyett
    - Adatbázis alapú naplózás a fejlesztéshez
    """
    
    def get_response(self, user, context_app, query=None):
        profile = getattr(user, 'profile', None)
        has_profile_name = bool(profile and profile.first_name and profile.last_name)
        
        user_roles = []
        if hasattr(user, 'user_roles'):
            user_roles = list(
                user.user_roles.filter(status='approved')
                .values_list('role__name', flat=True)
            )
        
        if query:
            # 1. NAVIGÁCIÓS KÉRDÉS KERESÉSE
            if self.is_navigation_question(query):
                loc = self.get_navigation_location(query, user_roles)
                if loc and "❓" not in loc:
                    return f"📍 Itt találod: {loc}"
                
                # Ha bizonytalan a helyszín, naplózunk és AI válaszol
                self._log_missed_query(user, query, context_app)
                prompt = f"A felhasználó navigációról kérdez: '{query}'. Segíts neki a DigiT-Train felületén eligazodni."
                return self._generate(prompt)
            
            # 2. SZAKMAI KÉRDÉS (Upsell)
            elif self.is_analytical_question(query):
                billing_url = reverse('billing:subscription_plans')
                return (
                    f"🔒 Ez egy szakmai kérdés, amihez **ML_ACCESS** előfizetés szükséges! "
                    f"Vásárolj előfizetést az adatok mélyreható elemzéséhez: "
                    f"<a href='{billing_url}' class='fw-bold'>Előfizetési tervek</a>"
                )
            
            # 3. ISMERETLEN KÉRDÉS -> AI válasz + Adatbázis mentés
            else:
                self._log_missed_query(user, query, context_app)
                
                prompt = (
                    f"A felhasználó kérdése: '{query}'. "
                    "Válaszolj mint egy digitális asszisztens. "
                    "Mondd el, hogy a menüben segítesz eligazodni, de az adatok elemzéséhez előfizetés kell."
                )
                return self._generate(prompt)
        
        return self._get_smart_welcome(user, context_app, has_profile_name, user_roles)

    def _log_missed_query(self, user, query, context_app):
        """Mentés a megadott DittaMissedQuery modellbe."""
        try:
            DittaMissedQuery.objects.create(
                user=user,
                query=query, # A te modelledben 'query' a mezőnév
                context_app=context_app,
                context_snapshot={
                    "detected_as": "Navigator",
                    "timestamp_day": date.today().isoformat()
                }
            )
        except Exception as e:
            # Csak konzolra írjuk a hibát, hogy a felhasználó ne lássa
            print(f"DEBUG: DittaMissedQuery mentési hiba: {e}")

    def get_navigation_location(self, query, user_roles):
        """Keresés a UI_NAVIGATION_MAP-ben kulcsszavak alapján"""
        query_lower = query.lower()
        
        for key, data in UI_NAVIGATION_MAP.items():
            # Megnézzük a leírást és a kulcsszavakat (ha lennének)
            search_text = f"{data.get('leírás', '')} {key}".lower()
            if any(word in query_lower for word in search_text.split() if len(word) > 3):
                # Ellenőrizzük a szerepkör jogosultságot
                req_role = data.get('szerepkör', 'Mindenki')
                if req_role != 'Mindenki' and req_role not in user_roles:
                    return f"⚠️ Ehhez {req_role} szerepkör szükséges!"
                return data.get('lokáció', 'a menüben')
        
        return "❓ Pontosíts: profil / mérés / kredit / szerepkörök"

    def _get_smart_welcome(self, user, context_app, has_profile_name, user_roles):
        """
        Kontextus-érzékeny üdvözlő üzenetek.
        
        Args:
            user: Felhasználó
            context_app: Jelenlegi oldal kontextusa
            has_profile_name: Van-e neve a felhasználónak
            user_roles: Felhasználó szerepkörei
        """
        from ml_engine.ai_coach.ui_knowledge import UI_NAVIGATION_MAP
        
        profile_url = reverse('users:edit_profile') 
        role_url = reverse('users:role_dashboard')
        
        display_name = user.profile.last_name if has_profile_name else user.username
        
        # 1. Profil hiány
        if not has_profile_name:
            return f"👋 Szia {user.username}! Ditta vagyok. Kérlek, add meg a neved a <a href='{profile_url}'>👤 Profilodnál</a>!"
        
        # 2. Szerepkör hiány
        if not user_roles:
            return f"👋 Szia {display_name}! Válassz szerepkört az <a href='{role_url}'>⚙️ Vezérlőpultban</a>!"
        
        # 3. Kontextus-specifikus üdvözlés
        if context_app in UI_NAVIGATION_MAP:
            page_data = UI_NAVIGATION_MAP[context_app]
            page_desc = page_data.get('leírás', 'Oldal')
            
            # Emoji-s leírás
            return f"👋 Szia {display_name}! {page_desc}"
        
        # 4. Robot mód üdvözlések (speciális kontextusok)
        role_instructions = {
            'create_coach': "👔 Edzői jelentkezés mód. Segítek kiválasztani a klubodat és sportágadat.",
            'create_athlete': "⚽ Sportoló regisztráció. Segítek megtalálni a klubodat és edződet.",
            'create_parent': "👨‍👩‍👧 Szülői fiók. Segítek összekapcsolni a profilodat a gyermekedével.",
            'create_club_and_leader_role': "👑 Egyesületi vezető. Segítek létrehozni a klubodat.",
        }
        
        if context_app in role_instructions:
            return f"👋 Szia {display_name}! {role_instructions[context_app]}"
        
        # 5. Speciális kontextusok kezelése
        if context_app == 'main_page_has_pending_tasks':
            pending_list_url = reverse('core:main_page')
            return (
                f"👋 Szia {display_name}! ⚠️ Jóváhagyásra váró kéréseid érkeztek! "
                f"Nézd meg a <a href='{pending_list_url}' class='fw-bold text-danger'>főoldali értesítéseidet</a>!"
            )
        
        # 6. Alapértelmezett üdvözlés
        role_emoji = {
            'Sportoló': '⚽',
            'Edző': '👔',
            'Szülő': '👨‍👩‍👧',
            'Egyesületi vezető': '👑'
        }
        
        primary_role = user_roles[0] if user_roles else None
        emoji = role_emoji.get(primary_role, '👋')
        
        return f"{emoji} Szia {display_name}! Miben segíthetek ma?"