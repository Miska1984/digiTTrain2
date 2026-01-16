from ml_engine.models import UserPredictionResult

class MLEngineInterpreter:
    def __init__(self, target_user):
        self.target_user = target_user

    def get_ml_predictions(self):
        """
        Lekéri a legfrissebb ML jóslatokat: Formaindex és edzői tanács.
        """
        prediction = UserPredictionResult.objects.filter(
            user=self.target_user
        ).order_by('-predicted_at').first()

        if not prediction:
            return "Még nincs generált predikció (Formaindex) ehhez a sportolóhoz."

        # Formaindex értelmezése (1-10 skála)
        score = prediction.form_score
        status = "Kiváló" if score > 8 else "Megfelelő" if score > 5 else "Fáradt / Alacsony"

        summary = [
            f"--- AI Előrejelzés (ML Engine) ---",
            f"Aktuális Formaindex: {round(score, 1)}/10 ({status})",
            f"AI Tanács: {prediction.coach_advice or 'Nincs specifikus tanács.'}",
            f"Utolsó frissítés: {prediction.predicted_at.strftime('%Y-%m-%d %H:%M')}"
        ]

        return "\n".join(summary)