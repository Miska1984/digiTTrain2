# /app/assessment/admin.py

from django.contrib import admin
from .models import PlaceholderAthlete, PhysicalAssessment

# --- PlaceholderAthlete Admin (Kapcsolási pont!) ---
@admin.register(PlaceholderAthlete)
class PlaceholderAthleteAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'birth_date', 'sport', 'registered_user', 'has_user_profile')
    search_fields = ('last_name', 'first_name', 'club__name', 'sport__name')
    list_filter = ('sport', 'club', 'registered_user')
    
    # Ezzel a mezővel az admin felületen manuálisan összekapcsolhatja az edző a PH-t a User-rel!
    fields = ('last_name', 'first_name', 'birth_date', 'club', 'sport', 'registered_user')
    
    def has_user_profile(self, obj):
        return obj.registered_user is not None
    has_user_profile.boolean = True
    has_user_profile.short_description = 'Regisztrált?'


# --- PhysicalAssessment Admin ---
@admin.register(PhysicalAssessment)
class PhysicalAssessmentAdmin(admin.ModelAdmin):
    list_display = ('assessment_date', 'get_athlete_name', 'assessment_type', 'result_value', 'coach')
    search_fields = ('athlete_user__profile__last_name', 'athlete_placeholder__last_name', 'coach__profile__last_name')
    list_filter = ('assessment_type', 'assessment_date', 'coach')
    
    # A ModelAdmin.formfield_for_foreignkey metódussal biztosíthatjuk,
    # hogy egyszerre ne töltsék ki mindkét sportoló mezőt, de a Django Adminban ez alapvetően manuális odafigyelést igényel.
    
    # Segédfüggvény a sportoló nevének megjelenítésére
    def get_athlete_name(self, obj):
        return obj.get_athlete_name()
    get_athlete_name.short_description = 'Sportoló'