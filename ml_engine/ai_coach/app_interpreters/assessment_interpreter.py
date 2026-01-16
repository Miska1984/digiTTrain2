from assessment.models import PhysicalAssessment, PlaceholderAthlete

class AssessmentInterpreter:
    def __init__(self, viewer_user):
        self.viewer = viewer_user

    def get_assessment_summary(self, target_user=None, athlete_name=None):
        """
        Lekéri a felméréseket. Ha target_user van, regisztráltat néz. 
        Ha csak név, megpróbálja a placeholder-ek között.
        """
        query = PhysicalAssessment.objects.all()
        
        if target_user:
            query = query.filter(athlete_user=target_user)
        elif athlete_name:
            query = query.filter(athlete_placeholder__first_name__icontains=athlete_name)
        else:
            return "Nincs megadva sportoló a felmérés kereséséhez."

        results = query.order_by('-assessment_date')[:5]
        
        if not results.exists():
            return "Erről a sportolóról még nincsenek rögzített fizikai felmérések (húzódzkodás, ugrás, stb.)."

        data_lines = []
        for r in results:
            data_lines.append(f"- {r.assessment_date}: {r.get_assessment_type_display()} = {r.result_value}")
        
        return "\n".join(data_lines)