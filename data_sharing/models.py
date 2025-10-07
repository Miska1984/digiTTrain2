# data_sharing/models.py
from django.db import models
from django.conf import settings


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

    def __str__(self):
        status = "✅" if self.enabled else "❌"
        return f"{status} {self.user.username} → {self.target_user.username}: {self.app_name}.{self.table_name}"
    
    @classmethod
    def is_data_shared(cls, data_owner, data_viewer, app_name, table_name):
        """
        Ellenőrzi, hogy a data_owner megosztotta-e az adott táblát a data_viewer-rel.
        Kezeli az 'ALL' engedélyt és a kis-/nagybetű eltéréseket is.
        """
        try:
            # Kisbetűs normalizálás
            app_name = app_name.lower()
            table_name = table_name.lower()

            # 1️⃣ Külön táblára vonatkozó engedély
            if cls.objects.filter(
                user=data_owner,
                target_user=data_viewer,
                app_name__iexact=app_name,
                table_name__iexact=table_name,
                enabled=True
            ).exists():
                return True

            # 2️⃣ Általános "ALL" engedély
            if cls.objects.filter(
                user=data_owner,
                target_user=data_viewer,
                app_name__iexact=app_name,
                table_name__iexact="all",
                enabled=True
            ).exists():
                return True

            return False

        except Exception as e:
            print("⚠️ is_data_shared() hiba:", e)
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