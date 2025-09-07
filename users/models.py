# users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
import logging
import os


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
    # A fájlnév a felhasználónevet és az eredeti fájlnevet fogja tartalmazni
    # a Cloud Storage útvonala pedig 'media/profile_pics/' lesz
    return os.path.join('media', 'profile_pics', f'{instance.user.username}_{filename}')

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    GENDER_CHOICES = (
        ('M', 'Férfi'),
        ('F', 'Nő'),
        ('O', 'Más')
    )
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    
    profile_picture = models.ImageField(default='profile_pics/default.jpg', upload_to=profile_picture_upload_path)

    def __str__(self):
        return f'{self.user.username} Profile'