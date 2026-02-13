# ml_engine/ai_coach/app_interpreters/ml_engine_interpreter.py

from ml_engine.models import UserPredictionResult

class MLEngineInterpreter:
    def __init__(self, target_user):
        self.target_user = target_user

    def get_ml_predictions(self):
        """
        Lekéri a legfrissebb ML jóslatokat: Formaindex és edzői tanács.
        Kezeli a 0-100 és 0-10 közötti bemeneti skálákat is a konzisztencia érdekében.
        """
        prediction = UserPredictionResult.objects.filter(
            user=self.target_user
        ).order_by('-predicted_at').first()

        if not prediction:
            return "Még nincs generált predikció (Formaindex) ehhez a sportolóhoz."

        # === DINAMIKUS SKÁLÁZÁS ÉS JAVÍTÁS ===
        raw_score = prediction.form_score
        
        # Ha az érték 10-nél nagyobb (pl. 61.5), akkor feltételezzük a 100-as skálát és osztjuk
        if raw_score > 10:
            display_score = round(raw_score / 10, 1)
        else:
            display_score = round(raw_score, 1)

        # Biztonsági korlát: a pontszám sosem lehet több 10.0-nál
        display_score = min(display_score, 10.0)

        # Státusz meghatározása az új skála alapján
        if display_score >= 8.0:
            status = "Kiváló"
        elif display_score >= 5.0:
            status = "Megfelelő"
        else:
            status = "Fáradt / Alacsony"

        # Összefoglaló összeállítása Dittának
        summary = [
            f"--- AI Előrejelzés (ML Engine) ---",
            f"Aktuális Formaindex: {display_score}/10 ({status})",
            f"AI Tanács: {prediction.coach_advice or 'Nincs specifikus tanács.'}",
            f"Utolsó frissítés: {prediction.predicted_at.strftime('%Y-%m-%d %H:%M')}"
        ]

        return "\n".join(summary)