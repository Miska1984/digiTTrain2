# /app/training_log/models.py

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from assessment.models import PlaceholderAthlete 
from users.models import Club, Sport, User

User = get_user_model()

# --- 1. TrainingSession ---
class TrainingSession(models.Model):
    """
    Egy adott edzés (hívás) időpontját, helyét és hívó edzőjét rögzíti.
    """
    coach = models.ForeignKey(User, on_delete=models.CASCADE, 
                              limit_choices_to={'role__name': 'Edző'}, 
                              verbose_name="Edző (hívó)")
    session_date = models.DateField(verbose_name="Dátum")
    start_time = models.TimeField(verbose_name="Kezdés ideje")
    duration_minutes = models.IntegerField(verbose_name="Időtartam (perc)")
    location = models.CharField(max_length=255, verbose_name="Helyszín", blank=True)
    
    def __str__(self):
        return f"Edzés: {self.session_date} - {self.coach.profile.last_name}"
        
    class Meta:
        verbose_name = "Edzés Hívás"
        verbose_name_plural = "Edzés Hívások"


# --- 2. Attendance ---
class Attendance(models.Model):
    """
    Rögzíti a sportolók jelenlétét egy adott TrainingSession-ön.
    """
    session = models.ForeignKey(TrainingSession, on_delete=models.CASCADE, 
                                related_name='attendees', verbose_name="Edzés")
    
    # Kapcsolat a kétféle sportolóhoz:
    registered_athlete = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                           related_name='attendances', verbose_name="Regisztrált Sportoló")
    placeholder_athlete = models.ForeignKey(PlaceholderAthlete, on_delete=models.CASCADE, null=True, blank=True, 
                                            related_name='attendances', verbose_name="Ideiglenes Sportoló")
    
    # Jelenlét és Edzés Visszajelzés
    is_present = models.BooleanField(default=False, verbose_name="Jelenlét")
    is_injured = models.BooleanField(default=False)
    is_guest = models.BooleanField(default=False)
    rpe_score = models.IntegerField(null=True, blank=True, verbose_name="Edzés RPE (1-10)")
    
    def get_athlete_name(self):
        if self.registered_athlete:
            return f"{self.registered_athlete.profile.last_name} {self.registered_athlete.profile.first_name}"
        elif self.placeholder_athlete:
            return f"{self.placeholder_athlete.last_name} {self.placeholder_athlete.first_name} (PH)"
        return "N/A"

    def __str__(self):
        return f"{self.session} - {self.get_athlete_name()} ({'Jelen' if self.is_present else 'Hiányzik'})"
        
    class Meta:
        verbose_name = "Edzés Jelenlét"
        verbose_name_plural = "Edzés Jelenlétek"


class AbsenceSchedule(models.Model):
    """
    Globális szünetek és leállások kezelése (pl. nyári szünet, nemzeti ünnepek).
    Ez befolyásolja az összes TrainingSchedule-t.
    """
    name = models.CharField(max_length=100, verbose_name="Szünet neve")
    start_date = models.DateField(verbose_name="Kezdő dátum")
    end_date = models.DateField(verbose_name="Befejező dátum")
    
    # Kategóriák: hogy könnyebb legyen szűrni (pl. "Nemzeti ünnep", "Iskolai szünet")
    CATEGORY_CHOICES = [
        ('NAT', 'Nemzeti/Állami Ünnep'),
        ('SCH', 'Iskolai/Oktatási Szünet'),
        ('WNT', 'Téli Leállás'),
        ('SUM', 'Nyári Szünet'),
        ('OTH', 'Egyéb')
    ]
    category = models.CharField(max_length=3, choices=CATEGORY_CHOICES, default='OTH', verbose_name="Kategória")
    
    # Opcionális: a Klubhoz rendelés (pl. ha csak az adott klubnak van leállása)
    club = models.ForeignKey(Club, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Egyesület")

    class Meta:
        verbose_name = "Szünet/Leállás"
        verbose_name_plural = "Szünetek/Leállások"
        ordering = ['start_date']

    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"


class TrainingSchedule(models.Model):
    DAY_CHOICES = [
        (1, 'Hétfő'), (2, 'Kedd'), (3, 'Szerda'), (4, 'Csütörtök'),
        (5, 'Péntek'), (6, 'Szombat'), (7, 'Vasárnap'),
    ]
    
    GENDER_CHOICES = [
        ('M', 'Fiú'),
        ('F', 'Lány'),
    ]

    club = models.ForeignKey(Club, on_delete=models.CASCADE, verbose_name="Egyesület")
    sport = models.ForeignKey(Sport, on_delete=models.CASCADE, verbose_name="Sportág")
    coach = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'user_roles__role__name': 'Edző'},
        verbose_name="Felelős Edző"
    )
    name = models.CharField(max_length=100, verbose_name="Edzéscsoport neve (Pl. U10 fiúk)")

    # Napok
    days_of_week = models.CharField(
        _("Napok"), 
        max_length=15, 
        help_text="Vesszővel elválasztott napok: 1=Hétfő, 7=Vasárnap."
    )
    
    # Időpontok
    start_time = models.TimeField(verbose_name="Kezdés időpontja")
    end_time = models.TimeField(verbose_name="Befejezés időpontja")
    
    # Életkor szerinti szűrés
    birth_years = models.CharField(
        _("Születési évek"), 
        max_length=100, 
        help_text="Vesszővel elválasztott születési évek."
    )

    # 🔧 JAVÍTOTT: itt nem használunk choices-t
    genders = models.CharField(
        _("Nemek"), 
        max_length=10, 
        help_text="Kiválasztott nemek (pl. M,F)."
    )

    # Érvényességi tartomány
    start_date = models.DateField(default=timezone.now, verbose_name="Érvényesség kezdete")
    end_date = models.DateField(null=True, blank=True, verbose_name="Érvényesség vége (Opcionális)")

    class Meta:
        verbose_name = "Edzésrend"
        verbose_name_plural = "Edzésrendek"
        ordering = ['start_time', 'club__name']

    def __str__(self):
        return f"{self.name} - {self.start_time.strftime('%H:%M')} ({self.birth_years})"
