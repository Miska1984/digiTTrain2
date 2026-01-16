    # training_log_interpreter.py

from training_log.models import TrainingSession, Attendance
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Sum

class TrainingLogInterpreter:
    def __init__(self, target_user):
        self.target_user = target_user
        self.now = timezone.now().date()
        self.start_date = self.now - timedelta(days=30)

    def get_training_summary(self):
        # Az utolsó 30 napot nézzük
        last_month = timezone.now() - timedelta(days=30)
        
        # JAVÍTÁS: athlete_user HELYETT registered_athlete
        attendances = Attendance.objects.filter(
            registered_athlete=self.target_user, 
            session__session_date__gte=last_month
        ).select_related('session')

        if not attendances.exists():
            return "Nincs rögzített edzéslátogatás az elmúlt 30 napban."

        total_sessions = attendances.count()
        present_count = attendances.filter(is_present=True).count()
        # Itt is javítva a mezőnév (session__duration_minutes)
        total_minutes = sum(a.session.duration_minutes for a in attendances if a.is_present)

        summary = [
            f"--- Edzésstatisztika (utolsó 30 nap) ---",
            f"Összes kiírt edzés: {total_sessions}",
            f"Részvétel: {present_count} alkalom",
            f"Edzésen töltött idő: {total_minutes} perc",
            f"Részvételi arány: {round((present_count/total_sessions)*100, 1)}%"
        ]

        return "\n".join(summary)