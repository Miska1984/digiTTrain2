import json
from django.utils.safestring import mark_safe
from django.contrib import admin
from .models import UserFeatureSnapshot, UserPredictionResult, DittaMissedQuery

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

# --- ÚJ: Itt követheted Ditta "hiányosságait" ---
@admin.register(DittaMissedQuery)
class DittaMissedQueryAdmin(admin.ModelAdmin):
    # Megjelenítendő oszlopok a listában
    list_display = ('created_at', 'user', 'short_query', 'context_app')
    
    # Szűrési lehetőségek
    list_filter = ('created_at', 'context_app')
    
    # Keresőmező
    search_fields = ('user__email', 'user__username', 'query')
    
    # Minden mező csak olvasható legyen, hiszen ez egy napló
    readonly_fields = ('user', 'query', 'context_app', 'formatted_context', 'created_at')
    
    # Kivesszük a nyers context_snapshotot és betesszük a formázott verziót
    exclude = ('context_snapshot',)

    def short_query(self, obj):
        """A kérdés elejének megjelenítése a listában."""
        return obj.query[:50] + "..." if len(obj.query) > 50 else obj.query
    short_query.short_description = "Felhasználó kérdése"

    def formatted_context(self, obj):
        """A JSON snapshot szép, olvasható megjelenítése az adatlapont."""
        if obj.context_snapshot:
            # Szépen formázott JSON-t csinálunk belőle HTML-ben
            formatted = json.dumps(obj.context_snapshot, indent=4, ensure_ascii=False)
            return mark_safe(f"<pre style='background: #f4f4f4; padding: 10px; border-radius: 5px;'>{formatted}</pre>")
        return "Nincs rögzített kontextus."
    formatted_context.short_description = "Ditta által látott adatok (Snapshot)"