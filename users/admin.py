from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Profile, Sport, Role, Club, UserRole, ParentChild

# User regisztráció, hogy lásd a felhasználókat
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')
    # Itt használhatod a gyári Django UserAdmin-t

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'first_name', 'last_name', 'date_of_birth', 'gender')
    search_fields = ('user__username', 'first_name', 'last_name')
    
    # Itt az adminban nincs korlátozás, bármit módosíthatsz.
    # A date_of_birth mező szerkeszthető marad.
    fields = ('user', 'first_name', 'last_name', 'date_of_birth', 'gender', 'profile_picture')

@admin.register(Sport)
class SportAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')
    list_filter = ('category',)
    search_fields = ('name',)
    list_editable = ('category',)

@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_name', 'address') 
    search_fields = ('name', 'short_name')

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'club', 'role', 'status')
    list_filter = ('club', 'role', 'status')
    search_fields = ('user__username', 'user__email', 'club__name')
    list_editable = ('status',) # Így az adminból is gyorsan jóváhagyhatsz

@admin.register(ParentChild)
class ParentChildAdmin(admin.ModelAdmin):
    list_display = ('parent', 'child', 'status', 'created_at')
    list_filter = ('status',)