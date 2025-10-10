from django.contrib import admin
from .models import DiagnosticJob

@admin.register(DiagnosticJob)
class DiagnosticJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'sport_type', 'job_type', 'status', 'created_at', 'completed_at')
    list_filter = ('status', 'job_type', 'sport_type')
    search_fields = ('user__username', 'sport_type')
    ordering = ('-created_at',)
