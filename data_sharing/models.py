# data_sharing/models.py
from django.db import models
from django.conf import settings


''' Régi Megosztási medel
class BiometricSharingPermission(models.Model):
    """
    Biometriai adatok megosztási engedélyei.
    Sportoló/Szülő dönti el, hogy mely táblák adatait osztja meg kivel.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='shared_permissions',
        verbose_name="Adatokat megosztó felhasználó"
    )
    
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='received_permissions',
        verbose_name="Adatokat fogadó felhasználó"
    )
    
    app_name = models.CharField(
        max_length=100,
        verbose_name="Alkalmazás neve",
        help_text="pl. 'biometric_data'"
    )
    
    table_name = models.CharField(
        max_length=100,
        verbose_name="Tábla neve", 
        help_text="pl. 'WeightData'"
    )
    
    enabled = models.BooleanField(
        default=False,
        verbose_name="Engedélyezve",
        help_text="Be van-e kapcsolva a megosztás"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Létrehozás időpontja"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Utolsó módosítás időpontja"
    )

    # A sportoló saját döntése
    athlete_consent = models.BooleanField(
        default=False, 
        verbose_name="Sportoló beleegyezése"
    )

    # A szülői felügyeleti jóváhagyás
    parent_consent = models.BooleanField(
        default=False, 
        verbose_name="Szülői jóváhagyás"
    )

    class Meta:
        unique_together = ('user', 'target_user', 'app_name', 'table_name')
        verbose_name = "Biometriai adat megosztási engedély"
        verbose_name_plural = "Biometriai adat megosztási engedélyek"
        ordering = ['-updated_at', 'app_name', 'table_name']
        indexes = [
            models.Index(fields=['user', 'enabled']),
            models.Index(fields=['target_user', 'enabled']),
            models.Index(fields=['app_name', 'table_name']),
        ]
    
    def save(self, *args, **kwargs):
        """
        Automatikus jogosultság-kezelés:
        - Ha kiskorú: enabled = sportoló ÉS szülő jóváhagyása kell.
        - Ha nagykorú: enabled = csak a sportoló jóváhagyása kell.
        """
        # A User modell property-jét használjuk, az már tudja a date_of_birth-et kezelni
        is_adult = self.user.is_adult

        if is_adult:
            # Nagykorú esetén csak a sportoló beleegyezése számít
            self.enabled = self.athlete_consent
        else:
            # Kiskorú esetén mindkét beleegyezés szükséges
            self.enabled = self.athlete_consent and self.parent_consent
        
        super().save(*args, **kwargs)

    def __str__(self):
        status = "✅" if self.enabled else "❌"
        return f"{status} {self.user.username} → {self.target_user.username}: {self.app_name}.{self.table_name}"
    
    @classmethod
    def is_data_shared(cls, data_owner, data_viewer, app_name, table_name):
        """
        Ellenőrzi, hogy a data_owner megosztotta-e az adott táblát a data_viewer-rel
        """
        try:
            permission = cls.objects.get(
                user=data_owner,
                target_user=data_viewer,
                app_name=app_name,
                table_name=table_name
            )
            return permission.enabled
        except cls.DoesNotExist:
            return False
    
    @classmethod
    def get_shared_data_owners(cls, viewer, app_name, table_name):
        """
        Visszaadja azokat a felhasználókat, akik megosztották az adott táblájukat a viewer-rel
        """
        return cls.objects.filter(
            target_user=viewer,
            app_name=app_name,
            table_name=table_name,
            enabled=True
        ).select_related('user')
    
    def toggle(self):
        """
        Átváltja az engedély státuszát
        """
        self.enabled = not self.enabled
        self.save(update_fields=['enabled', 'updated_at'])
        return self.enabled
'''

# ÚJ MODELL - A TISZTA LAP
class DataSharingPermission(models.Model):
    # Az adat tulajdonosa (Mindig Sportoló)
    athlete = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='permissions_given'
    )
    
    # Aki látni szeretné (Edző, Vezető, Szülő)
    target_person = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='permissions_received'
    )
    
    # Milyen minőségben? (MBSZ edző, TBDSK vezető, stb.)
    # Ha ez törlődik (kikerül a keretből), a megosztás is törlődik.
    target_role = models.ForeignKey(
        'users.UserRole', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )

    app_name = models.CharField(max_length=100)
    table_name = models.CharField(max_length=100)

    # A két kulcs a zárhoz
    athlete_consent = models.BooleanField(default=False)
    parent_consent = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Adatmegosztási engedély"
        verbose_name_plural = "Adatmegosztási engedélyek"
        # Biztosítjuk, hogy egy szerepkörhöz/adathoz ne legyen dupla sor
        unique_together = ('athlete', 'target_person', 'target_role', 'app_name', 'table_name')

    def __str__(self):
        return f"{self.athlete.username} -> {self.target_person.username} ({self.table_name})"