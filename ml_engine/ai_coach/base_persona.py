# base_persona.py
from google import genai  # Új import
from django.conf import settings

class BasePersona:
    def __init__(self):
        # Az új kliens inicializálása
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_id = "gemini-2.0-flash-exp" # Vagy a használni kívánt modell

    def _generate(self, prompt):
        """Központi generáló metódus minden persona számára."""
        try:
            full_prompt = (
                "Te Ditta vagy, a DigiT-Train intelligens coach asszisztense. "
                "Mindig magyarul válaszolj. Légy közvetlen (tegeződj), motiváló és szakmai. "
                f"\n\nFeladat/Kontextus: {prompt}"
            )
            # Az új generálási szintaxis
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=full_prompt
            )
            return response.text
        except Exception as e:
            return f"Szia! Egy kis technikai zavar támadt az agyamban (Hiba: {str(e)})"