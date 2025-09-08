# users/admin.py
from django.contrib import admin
from .models import Sport, Role, Club, UserRole

admin.site.register(Sport)
admin.site.register(Role)
admin.site.register(Club)
admin.site.register(UserRole)


