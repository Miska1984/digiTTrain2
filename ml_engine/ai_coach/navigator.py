# ml_engine/ai_coach/navigator.py
from .base_persona import BasePersona
from django.urls import reverse
from datetime import date

class NavigatorPersona(BasePersona):
    """
    Navigator (Asszisztens) mód - INGYENES, mindenki számára elérhető
    
    Feladatai:
    1. Navigációs segítség → ui_knowledge.py alapján
    2. Szakmai kérdések → "ML előfizetés szükséges!"
    3. Ismeretlen kérdések → [MISSED] jelzés fejlesztőknek
    """
    
    def get_response(self, user, context_app, query=None):
        """
        Navigator válasz generálása.
        
        Args:
            user: A felhasználó
            context_app: Az alkalmazás kontextusa
            query: A felhasználó kérdése (ha van)
        
        Returns:
            str: Ditta válasza
        """
        profile = getattr(user, 'profile', None)
        has_profile_name = bool(profile and profile.first_name and profile.last_name)
        
        # Felhasználó szerepköreinek lekérése
        user_roles = []
        if hasattr(user, 'user_roles'):
            user_roles = list(
                user.user_roles.filter(status='approved')
                .values_list('role__name', flat=True)
            )
        
        # Ha van kérdés, azt dolgozzuk fel
        if query:
            # 1. NAVIGÁCIÓS KÉRDÉS?
            if self.is_navigation_question(query):
                return self.answer_navigation_question(query, user_roles)
            
            # 2. SZAKMAI/ELEMZŐ KÉRDÉS?
            elif self.is_analytical_question(query):
                billing_url = reverse('billing:billing_purchase')
                return (
                    f"🔒 Ehhez ML_ACCESS előfizetés szükséges! "
                    f"Csak előfizetőknek tudom elemezni az adatokat. "
                    f"<a href='{billing_url}' class='fw-bold'>Vásárlás itt</a>"
                )
            
            # 3. ISMERETLEN KÉRDÉS
            else:
                return (
                    f"[MISSED] Hmm, ezt még nem tanultam meg! 🤔 "
                    f"De jelzem a fejlesztőknek, hogy segíthessek legközelebb!"
                )
        
        # Ha nincs kérdés, üdvözlő üzenetet adunk kontextus alapján
        return self._get_smart_welcome(user, context_app, has_profile_name, user_roles)

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