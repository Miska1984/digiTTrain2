from django.contrib import admin
from .models import WeightData, HRVandSleepData, WorkoutFeedback, RunningPerformance

@admin.register(WeightData)
class WeightDataAdmin(admin.ModelAdmin):
    list_display = ('user', 'workout_date', 'morning_weight', 'created_at')
    # A workout_date most már szerkeszthető lesz az adminban!
    fields = ('user', 'workout_date', 'morning_weight', 'pre_workout_weight', 'post_workout_weight', 'fluid_intake', 'body_fat_percentage', 'muscle_percentage', 'bone_mass_kg')

@admin.register(HRVandSleepData)
class HRVandSleepDataAdmin(admin.ModelAdmin):
    list_display = ('user', 'recorded_at', 'hrv', 'sleep_quality')
    fields = ('user', 'recorded_at', 'hrv', 'sleep_quality', 'alertness')

@admin.register(WorkoutFeedback)
class WorkoutFeedbackAdmin(admin.ModelAdmin):
    list_display = ('user', 'workout_date', 'workout_intensity')
    fields = ('user', 'workout_date', 'workout_intensity', 'right_grip_strength', 'left_grip_strength')

@admin.register(RunningPerformance)
class RunningPerformanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'run_date', 'run_distance_km', 'run_duration')
    fields = ('user', 'run_date', 'run_distance_km', 'run_duration', 'run_min_hr', 'run_max_hr', 'run_avg_hr')