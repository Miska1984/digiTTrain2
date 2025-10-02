# /app/assessment/models.py

from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from users.models import Club, Sport 

User = get_user_model()

# --- 1. PlaceholderAthlete ---
class PlaceholderAthlete(models.Model):
    """
    Ideiglenes modell regisztrálatlan sportolók edzésadatainak tárolására.
    """
    GENDER_CHOICES = [
        ('M', 'Fiú'),
        ('F', 'Lány'),
    ]

    first_name = models.CharField(max_length=100, verbose_name="Keresztnév")
    last_name = models.CharField(max_length=100, verbose_name="Vezetéknév")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Születési dátum")
    club = models.ForeignKey(Club, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Egyesület")
    sport = models.ForeignKey(Sport, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sportág")
    
    # Ez a mező lesz a kulcs az adatok migrálásakor!
    registered_user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                           related_name='placeholder_record', 
                                           verbose_name="Regisztrált Felhasználó")

    gender = models.CharField(
        _("Nem"), 
        max_length=1, 
        choices=GENDER_CHOICES, 
        default='M' # Vagy a leggyakoribb érték, ha van
    )

    def __str__(self):
        return f"PH: {self.last_name} {self.first_name}"
        
    class Meta:
        verbose_name = "Ideiglenes Sportoló"
        verbose_name_plural = "Ideiglenes Sportolók"


# --- 2. PhysicalAssessment ---
class PhysicalAssessment(models.Model):
    """
    Az edző által végzett fizikai felmérések rögzítésére szolgál.
    """
    coach = models.ForeignKey(User, on_delete=models.CASCADE, 
                              limit_choices_to={'role__name': 'Edző'}, 
                              verbose_name="Felmérést végző Edző")
    assessment_date = models.DateField(verbose_name="Dátum")

    # Kapcsolat a sportolóhoz (csak az egyik lehet kitöltve!)
    athlete_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                     related_name='physical_assessments', verbose_name="Regisztrált Sportoló")
    athlete_placeholder = models.ForeignKey(PlaceholderAthlete, on_delete=models.CASCADE, null=True, blank=True, 
                                            related_name='physical_assessments', verbose_name="Ideiglenes Sportoló")

    # A Felmérés Adatai:
    ASSESSMENT_CHOICES = [
        ('GRIP_STRENGTH', 'Markoerő (kg)'),
        ('PULL_UPS', 'Húzódzkodás (ismétlés)'),
        ('YO_YO', 'Ingafutás (szint)'),
        ('JUMP_HEIGHT', 'Ugrás Magasság (cm)'),
        ('WEIGHT', 'Testsúly (kg)'),
    ]
    
    assessment_type = models.CharField(max_length=50, choices=ASSESSMENT_CHOICES, verbose_name="Felmérés Típusa")
    result_value = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Eredmény")
    notes = models.TextField(blank=True, verbose_name="Megjegyzések")

    def __str__(self):
        athlete_name = self.athlete_user.profile.last_name if self.athlete_user else self.athlete_placeholder.last_name
        return f"{athlete_name} - {self.get_assessment_type_display()} ({self.assessment_date})"

    class Meta:
        verbose_name = "Edzői Felmérés"
        verbose_name_plural = "Edzői Felmérések"