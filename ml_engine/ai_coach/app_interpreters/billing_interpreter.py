from billing.models import UserSubscription, UserCreditBalance, UserAnalysisBalance
from django.utils import timezone

class BillingInterpreter:
    def __init__(self, target_user):
        self.target_user = target_user

    def get_billing_status(self):
        # 1. Kredit egyenleg lekérése
        credit_obj = UserCreditBalance.objects.filter(user=self.target_user).first()
        credits = credit_obj.credits if credit_obj else 0

        # 2. Elemzési keret lekérése
        analysis_obj = UserAnalysisBalance.objects.filter(user=self.target_user).first()
        analysis_count = analysis_obj.count if analysis_obj else 0

        # 3. Aktív előfizetések (ML vagy Ad-Free)
        active_subs = UserSubscription.objects.filter(
            user=self.target_user,
            active=True,
            expiry_date__gte=timezone.now()
        )

        sub_list = []
        has_ml = False
        for sub in active_subs:
            sub_name = "ML Funkciók" if sub.sub_type == 'ML_ACCESS' else "Hirdetésmentesség"
            sub_list.append(f"{sub_name} (Lejár: {sub.expiry_date.strftime('%Y-%m-%d')})")
            if sub.sub_type == 'ML_ACCESS':
                has_ml = True

        status_report = [
            f"Kreditegyenleg: {credits} Cr",
            f"Elemzési keret: {analysis_count} db",
            f"Aktív előfizetések: {', '.join(sub_list) if sub_list else 'Nincs aktív előfizetés'}"
        ]
        
        if not has_ml:
            status_report.append("FIGYELEM: Az ML elemzésekhez (pl. Formaindex) aktív előfizetés szükséges.")

        return "\n".join(status_report)