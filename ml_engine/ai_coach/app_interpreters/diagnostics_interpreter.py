# diagnostics_interpreter.py

# 1. JAVÍTÁS: Az importnál használd azt a nevet, amit a hibaüzenet javasolt
from diagnostics_jobs.models import DiagnosticJob, UserAnthropometryProfile 

class DiagnosticsInterpreter:
    def __init__(self, target_user):
        self.target_user = target_user

    def get_diagnostics_summary(self):
        jobs = DiagnosticJob.objects.filter(
            user=self.target_user,
            status='COMPLETED'
        ).order_by('-created_at')[:3]

        # 2. JAVÍTÁS: Itt is írd át a modell nevét
        profile = UserAnthropometryProfile.objects.filter(user=self.target_user).first()

        if not jobs.exists() and not profile:
            return "Nincsenek elérhető diagnosztikai adatok vagy mozgáselemzések."

        summary = ["--- Diagnosztika és Mozgáselemzés ---"]
        
        if profile:
            summary.append(f"Testmagasság: {profile.height_cm or '?'} cm")
            # Figyelem! Ellenőrizd, hogy a 'manual_thigh_cm' létezik-e ebben a modellben!
            if hasattr(profile, 'manual_thigh_cm') and profile.manual_thigh_cm:
                summary.append(f"Regisztrált combhossz: {profile.manual_thigh_cm} cm")

        if jobs.exists():
            summary.append("Legutóbbi elemzések eredményei:")
            for job in jobs:
                summary.append(f"- {job.get_job_type_display()}: {job.updated_at.strftime('%Y-%m-%d')} (Sikeres)")
        
        return "\n".join(summary)