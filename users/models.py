# users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser


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

class Profile(models.Model):
    """
    A profilmodell, ami a felhasználóhoz kapcsolódik, de a felhasználó fiókja
    null is lehet. Ezzel tudunk adatokat tárolni azokról a gyerekekről,
    akiknek még nincs saját belépési lehetőségük.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    
    GENDER_CHOICES = (
        ('M', 'Férfi'),
        ('F', 'Nő'),
        ('O', 'Más')
    )
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)

    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)

    def __str__(self):
        if self.user:
            return f'{self.user.username} Profil'
        return f'Profil ({self.first_name} {self.last_name})'
    

