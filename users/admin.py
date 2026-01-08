from django.contrib import admin
from .models import Sport, Role, Club, UserRole

@admin.register(Sport)
class SportAdmin(admin.ModelAdmin):
    # Ezek az oszlopok fognak látszódni a listában
    list_display = ('name', 'category')
    
    # Oldalsó szűrő a kategóriák szerint
    list_filter = ('category',)
    
    # Keresési lehetőség a sportág neve alapján
    search_fields = ('name',)
    
    # Lehetőség a kategória gyors szerkesztésére közvetlenül a listából
    list_editable = ('category',)

@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    # Csak a nevet és a címet hagyjuk meg, amíg nem látjuk a pontos mezőneveket
    list_display = ('name', 'address') 
    search_fields = ('name',)

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'club', 'role')
    list_filter = ('club', 'role')
    search_fields = ('user__email', 'club__name')