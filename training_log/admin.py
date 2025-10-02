# /app/training_log/admin.py

from django.contrib import admin
from .models import TrainingSession, Attendance

# --- Attendance Inline ---
class AttendanceInline(admin.TabularInline):
    model = Attendance
    extra = 1  # Hány üres sor jelenjen meg alapból
    
    # A regisztrált és ideiglenes sportolóknak a lenyíló listáit megkülönböztetjük
    fields = ('registered_athlete', 'placeholder_athlete', 'is_present', 'rpe_score')
    
    # Megjegyzés: Külön logikát igényel, hogy csak a coach által kezelt sportolók jelenjenek meg itt!


# --- TrainingSession Admin ---
@admin.register(TrainingSession)
class TrainingSessionAdmin(admin.ModelAdmin):
    list_display = ('session_date', 'start_time', 'location', 'coach', 'duration_minutes')
    search_fields = ('location', 'coach__profile__last_name')
    list_filter = ('session_date', 'coach')
    inlines = [AttendanceInline]
    
    # Az edző automatikus beállítása a létrehozáskor
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.coach = request.user
        super().save_model(request, obj, form, change)
        
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Feltételezve, hogy csak az edzők férnek hozzá és csak a saját edzéseiket látják
        if request.user.is_superuser:
            return qs
        # Ez a logikai korlátozás beállítható, ha van egyértelmű szerepkör ellenőrzés
        return qs.filter(coach=request.user)