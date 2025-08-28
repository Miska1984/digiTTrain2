from django.db import models
from django.contrib.auth.models import User

# Szerepek definiálása
class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

# Sportágak definiálása
class Sport(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

# Egyesületek definiálása
class Association(models.Model):
    name = models.CharField(max_length=100, unique=True)
    sports = models.ManyToManyField(Sport, related_name='associations')

    def __str__(self):
        return self.name

# A User modell kibővítése profil adattal és szerepkörrel
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True)
    birth_date = models.DateField(null=True, blank=True)
    associations = models.ManyToManyField(Association, related_name='members')
    parent_of = models.ManyToManyField('self', related_name='children_profiles', symmetrical=False, blank=True)

    def __str__(self):
        return self.user.username
    