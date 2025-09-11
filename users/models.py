# users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
import logging
import os
import uuid


logger = logging.getLogger(__name__)

class User(AbstractUser):
    """
    Az egyedi User modell, amihez a szerepkörök kapcsolódnak.
    """
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='A felhasználó csoportjai. A felhasználó megkap minden jogosultságot, ami az összes csoportjához tartozik.',
        related_name="user_groups",  # Egyedi név hozzáadva
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Egyedi jogosultságok a felhasználó számára.',
        related_name="user_permissions_set",  # Egyedi név hozzáadva
        related_query_name="user",
    )

    def __str__(self):
        return self.username

def profile_picture_upload_path(instance, filename):
    # Generálunk egy egyedi UUID-t a fájlnévhez, így biztosan nem lesz ütközés
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    path = os.path.join("profile_pics", unique_filename)
    print(f"📂 Fájlfeltöltési útvonal generálva: {path}")
    return path

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    GENDER_CHOICES = (
        ('M', 'Férfi'),
        ('F', 'Nő'),
    )
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)

    # NINCS default, külön property-ben adjuk vissza a default.jpg-t
    profile_picture = models.ImageField(upload_to=profile_picture_upload_path, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} Profile"

    @property
    def profile_picture_url(self):
        if self.profile_picture:
            url = self.profile_picture.url
            print(f"🔗 Kép URL lekérve: {url}")
            return url
        print("⚠️ Nincs kép, default-ot adunk vissza")
        return settings.STATIC_URL + "images/default.jpg"  # legyen egy default kép a staticban
    
class Role(models.Model):
    # A szerepkörök listáját a kódban tároljuk
    ROLE_CHOICES = (
        ('Egyesületi vezető', 'Egyesületi vezető'),
        ('Edző', 'Edző'),
        ('Sportoló', 'Sportoló'),
        ('Szülő', 'Szülő'),
        ('Szurkoló', 'Szurkoló'),
    )
    name = models.CharField(max_length=50, choices=ROLE_CHOICES, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Sport(models.Model):
    # A sportágak listáját szintén a kódban tároljuk
    SPORT_CHOICES = (
        ('Kosárlabda', 'Kosárlabda'),
        ('Bírkozás', 'Bírkozás'),
        ('Labdarúgás', 'Labdarúgás'),
        ('Kézilabda', 'Kézilabda'),
        ('Vízilabda', 'Vízilabda'),
        ('Röplabda', 'Röplabda'),
        ('Asztalitenisz', 'Asztalitenisz'),
        ('Úszás', 'Úszás'),
    )
    name = models.CharField(max_length=50, choices=SPORT_CHOICES, unique=True)

    def __str__(self):
        return self.name

class Club(models.Model):
    name = models.CharField(max_length=200, unique=True)
    short_name = models.CharField(max_length=50, unique=True)
    address = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='club_logos/', blank=True, null=True)
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_clubs')
    
    # A sportágak many-to-many kapcsolatban vannak
    sports = models.ManyToManyField(Sport, related_name='clubs')

    def __str__(self):
        return self.name
        
class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    club = models.ForeignKey(Club, on_delete=models.CASCADE, null=True, blank=True)
    sport = models.ForeignKey(Sport, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = ('user', 'role', 'club', 'sport')

    def __str__(self):
        return f'{self.user.username} - {self.role.name}'

