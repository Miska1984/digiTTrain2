import os
import google.generativeai as genai
from .models import UserPredictionResult

class AICoachService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.model = None

    def generate_advice(self, user):
        from biometric_data.models import HRVandSleepData
        
        if not self.model:
            return "AI Coach nem elérhető: Hiányzó API kulcs."

        try:
            # 1. Legutóbbi ML predikció lekérése (form_score és predicted_at használatával)
            prediction = UserPredictionResult.objects.filter(user=user).latest('predicted_at')
            form_index = int(prediction.form_score * 100)
            
            # 2. Legutóbbi biometrikus adatok
            bio = HRVandSleepData.objects.filter(user=user).order_by('-recorded_at').first()
            
            hrv_val = bio.hrv if bio and bio.hrv else "Nincs adat"
            sleep_q = bio.get_sleep_quality_display() if bio and bio.sleep_quality else "Nincs adat"
            alertness = bio.get_alertness_display() if bio and bio.alertness else "Nincs adat"
            
            # 3. Prompt összeállítása
            prompt = f"""
            Te egy profi asztalitenisz szakedző vagy. Elemezd a játékos adatait:
            - Mai várható formaindex: {form_index}%
            - Utolsó mért HRV: {hrv_val} ms
            - Alvás minősége: {sleep_q}
            - Általános közérzet: {alertness}
            
            Adj egy rövid (2-3 mondatos), közvetlen hangvételű tanácsot a mai edzéshez. 
            Legyél szakmai, de támogató.
            """

            response = self.model.generate_content(prompt)
            advice_text = response.text
            
            # 4. Mentés a coach_advice mezőbe
            prediction.coach_advice = advice_text
            prediction.save()
            
            return advice_text
            
        except Exception as e:
            print(f"Hiba az AI Coach futása közben: {e}")
            return None