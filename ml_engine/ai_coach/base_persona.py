# base_persona.py
from google import genai
from django.conf import settings

class BasePersona:
    def __init__(self):
        # ÚJ SDK konfiguráció (google.genai - NEM deprecated!)
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_id = "gemini-2.0-flash"
        
    def is_navigation_question(self, query):
        """Felismeri navigációs kérdéseket"""
        if not query:
            return False
        query_lower = query.lower()
        navigation_keywords = [
            'hol', 'ahol', 'melyik', 'találom', 'található', 'hova',
            'hogyan', 'módosít', 'változtat', 'szerkeszt',
            'gomb', 'menü', 'oldal', 'link',
            'nem látom', 'nem találom', 'eltűnt',
            'profil', 'kép', 'fotó', 'mérés', 'rögzít',
            'vásárol', 'fizet', 'kredit', 'előfizetés',
            'sportoló', 'gyerek', 'gyermek', 'csapat',
            'megosztás', 'jogosultság', 'hozzáférés'
        ]
        return any(keyword in query_lower for keyword in navigation_keywords)
    
    def is_analytical_question(self, query):
        """Felismeri szakmai/elemző kérdéseket"""
        if not query:
            return False
        query_lower = query.lower()
        analytical_keywords = [
            'miért', 'mit jelent', 'értelmez', 'magyaráz',
            'hrv', 'formaindex', 'forma', 'terhelés', 'fáradtság',
            'elemzés', 'trend', 'predikció', 'előrejelzés',
            'javaslat', 'tanács', 'mit tegyek',
            'túlterhelés', 'pihenés', 'regeneráció',
            'teljesítmény', 'kondíció', 'pulzus',
            'súly', 'testsúly', 'testzsír',
            'edzésterv', 'program', 'fejlődés'
        ]
        return any(keyword in query_lower for keyword in analytical_keywords)
    
    def answer_navigation_question(self, query, user_roles=None):
        """Navigációs válasz ui_knowledge alapján"""
        from ml_engine.ai_coach.ui_knowledge import UI_NAVIGATION_MAP, FAQ_SHORTCUTS
        
        if not query:
            return "Miben segíthetek a navigációban?"
        
        query_lower = query.lower()
        
        # Gyors FAQ válaszok
        if any(kw in query_lower for kw in ['hrv', 'mér', 'reggel']):
            return FAQ_SHORTCUTS['hol_reggeli_mérés']['rövid']
        if any(kw in query_lower for kw in ['profil', 'kép', 'fotó']):
            return FAQ_SHORTCUTS['hol_profil']['rövid']
        if any(kw in query_lower for kw in ['kredit', 'vásár', 'fizet']):
            return FAQ_SHORTCUTS['hol_kredit_vásárlás']['rövid']
        if any(kw in query_lower for kw in ['sportoló', 'csapat']) and user_roles and 'Edző' in user_roles:
            return FAQ_SHORTCUTS['hol_sportolóim']['rövid']
        if any(kw in query_lower for kw in ['gyerek', 'gyermek']) and user_roles and 'Szülő' in user_roles:
            return FAQ_SHORTCUTS['hol_gyerekeim']['rövid']
        if any(kw in query_lower for kw in ['megosztás', 'jogosultság']):
            return FAQ_SHORTCUTS['hol_megosztás']['rövid']
        if any(kw in query_lower for kw in ['formaindex', 'forma', 'előrejelzés']):
            return FAQ_SHORTCUTS['mi_az_formaindex']['rövid']
        
        # UI_NAVIGATION_MAP keresés
        matching_pages = []
        for page_key, page_data in UI_NAVIGATION_MAP.items():
            page_text = f"{page_data.get('leírás', '')} {page_data.get('lokáció', '')}".lower()
            if any(word in page_text for word in query_lower.split() if len(word) > 3):
                matching_pages.append((page_key, page_data))
        
        if matching_pages:
            page_key, page_data = matching_pages[0]
            required_role = page_data.get('szerepkör', 'Mindenki')
            if required_role != 'Mindenki' and user_roles and required_role not in user_roles:
                return f"⚠️ Ehhez {required_role} szerepkör szükséges!"
            return page_data.get('lokáció', page_data.get('leírás', 'Oldal'))
        
        return "❓ Pontosíts: profil / mérés / kredit / sportolók / gyerekek"

    def _generate(self, prompt):
        """Generálás google.genai SDK-val (ÚJ, nem deprecated!)"""
        try:
            full_prompt = (
                "Te Ditta vagy, a DigiT-Train coach asszisztense. "
                "Magyarul válaszolj, tegeződj, légy motiváló. "
                "Rövid válaszok! Max 2-3 mondat. Használj emojit! "
                f"\n\n{prompt}"
            )
            
            # ÚJ SDK szintaxis
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=full_prompt
            )
            
            return response.text
            
        except Exception as e:
            return f"Szia! Technikai hiba: {str(e)}"