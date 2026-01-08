from django.contrib import admin
from .models import UserFeatureSnapshot, UserPredictionResult

@admin.register(UserFeatureSnapshot)
class UserFeatureSnapshotAdmin(admin.ModelAdmin):
    list_display = ('user', 'snapshot_date', 'generated_at')
    list_filter = ('snapshot_date', 'user')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('generated_at',)

@admin.register(UserPredictionResult)
class UserPredictionResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'form_score', 'source_date', 'predicted_at')
    list_filter = ('source_date', 'predicted_at')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('predicted_at',)