from django.contrib import admin
from .models import WeightData

class WeightDataAdmin(admin.ModelAdmin):
    list_display = ('user', 'morning_weight', 'pre_workout_weight', 'post_workout_weight', 'workout_date')
    list_filter = ('user', 'workout_date')
    search_fields = ('user__username',)

admin.site.register(WeightData, WeightDataAdmin)