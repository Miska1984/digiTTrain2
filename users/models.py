# users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import timezone
from datetime import date
import logging
import os
import uuid


logger = logging.getLogger(__name__)
logger.info("📦 Aktív storage backend: %s", default_storage.__class__)

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
    
    @property
    def is_adult(self):
        """Ellenőrzi, hogy 18 éves vagy annál idősebb-e"""
        if hasattr(self, 'profile') and self.profile.date_of_birth:
            from datetime import date
            today = date.today()
            age = today.year - self.profile.date_of_birth.year - (
                (today.month, today.day) < (self.profile.date_of_birth.month, self.profile.date_of_birth.day)
            )
            return age >= 18
        return True  # Ha nincs születési dátum, alapértelmezetten felnőtt
    
    def is_club_leader_in(self, club):
        """
        Ellenőrzi, hogy a felhasználó egyesületi vezető-e az adott klubban
        """
        return self.user_roles.filter(
            club=club,
            role__name="Egyesületi vezető",
            status="approved"
        ).exists()

def profile_picture_upload_path(instance, filename):
    # Generálunk egy egyedi UUID-t a fájlnévhez, így biztosan nem lesz ütközés
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    path = os.path.join("profile_pics", unique_filename)
    logger.info(f"📂 Fájlfeltöltési útvonal generálva: {path}")
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

    # EXPLICIT storage backend megadása!
    profile_picture = models.ImageField(
        upload_to=profile_picture_upload_path, 
        blank=True, 
        null=True,
    )

    def save(self, *args, **kwargs):
        """Override save method a részletes logginghoz"""
        if self.profile_picture:
            logger.info(f"💾 Profile mentése - fájl: {self.profile_picture.name}")
            logger.info(f"🔍 Storage backend: {self.profile_picture.storage.__class__}")
            print(f"💾 Profile mentése - fájl: {self.profile_picture.name}")
            print(f"🔍 Storage backend: {self.profile_picture.storage.__class__}")
        
        super().save(*args, **kwargs)
        
        if self.profile_picture:
            logger.info(f"✅ Profile mentve - fájl URL: {self.profile_picture.url}")
            print(f"✅ Profile mentve - fájl URL: {self.profile_picture.url}")

    def __str__(self):
        return f"{self.user.username} Profile"

    @property
    def profile_picture_url(self):
        if self.profile_picture:
            try:
                url = self.profile_picture.url
                logger.info(f"🔗 Kép URL lekérve: {url}")
                print(f"🔗 Kép URL lekérve: {url}")
                return url
            except Exception as e:
                logger.error(f"❌ Hiba a kép URL lekérésekor: {str(e)}")
                print(f"❌ Hiba a kép URL lekérésekor: {str(e)}")
                return settings.STATIC_URL + "images/default.jpg"
        logger.info("⚠️ Nincs kép, default-ot adunk vissza")
        print("⚠️ Nincs kép, default-ot adunk vissza")
        return settings.STATIC_URL + "images/default.jpg"  # legyen egy default kép a staticban    
        
    def age_years(self):
        """Kiszámolja a felhasználó életkorát években."""
        if self.date_of_birth:
            # Ugyanaz a logika, mint amit az is_adult property használ
            today = date.today()
            age = today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
            return age
        return None # Ha nincs születési dátum
    
class Role(models.Model):
    # A szerepkörök listáját a kódban tároljuk
    ROLE_CHOICES = (
        ('Egyesületi vezető', 'Egyesületi vezető'),
        ('Edző', 'Edző'),
        ('Sportoló', 'Sportoló'),
        ('Szülő', 'Szülő'),
        # Későbbre tartogatva:
        # ('Szurkoló', 'Szurkoló'),
        # ('Egyesületi adminisztrátor', 'Egyesületi adminisztrátor'),
    )
    name = models.CharField(max_length=50, choices=ROLE_CHOICES, unique=True)
    description = models.TextField(blank=True, default='')

    def __str__(self):
        return self.name

class Sport(models.Model):
    # ML kategóriák a számítási logika elkülönítéséhez
    CATEGORY_CHOICES = (
        ('COMBAT', 'Küzdősport (Birkózás, Judo, Vívás)'),
        ('TEAM', 'Csapatsport (Foci, Kézi, Vízilabda, Kosár)'),
        ('ENDURANCE', 'Állóképességi (Futás, Úszás, Kerékpár)'),
        ('POWER_TECH', 'Erő/Technikai (Súlylökés, Fitness, Dobóatlétika)'),
    )

    # A sportágak listáját szintén a kódban tároljuk
    SPORT_CHOICES = (
        ('Kosárlabda', 'Kosárlabda'),
        ('Birkózás', 'Birkózás'),
        ('Labdarúgás', 'Labdarúgás'),
        ('Kézilabda', 'Kézilabda'),
        ('Vízilabda', 'Vízilabda'),
        ('Röplabda', 'Röplabda'),
        ('Asztalitenisz', 'Asztalitenisz'),
        ('Úszás', 'Úszás'),
    )
    name = models.CharField(max_length=50, choices=SPORT_CHOICES, unique=True)
    category = models.CharField(
        max_length=20, 
        choices=CATEGORY_CHOICES, 
        default='TEAM' # Alapértelmezett, amit az adminban átállíthatsz
    )

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

def club_logo_upload_path(instance, filename):
    """Generálja a feltöltési útvonalat a klub logóknak"""
    # Hozzuk létre a mappát, ha még nem létezik
    upload_dir = os.path.join(settings.MEDIA_ROOT, 'club_logos')
    os.makedirs(upload_dir, exist_ok=True)

    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    return os.path.join('club_logos', unique_filename)

class Club(models.Model):
    name = models.CharField(max_length=200, unique=True)
    short_name = models.CharField(max_length=50, unique=True)
    address = models.CharField(max_length=255)
    logo = models.ImageField(upload_to=club_logo_upload_path, blank=True, null=True)
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_clubs')
    created_at = models.DateTimeField(auto_now_add=True)

    sports = models.ManyToManyField(Sport, related_name='clubs')

    def __str__(self):
        return self.name

# Ez a model nem került használtra!!!
class ParentChild(models.Model):
    """
    Szülő-gyerek kapcsolat modell
    """
    parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name="parentchild_children")
    child = models.ForeignKey(User, on_delete=models.CASCADE, related_name="parentchild_parents")
    
    STATUS_CHOICES = (
        ('pending', 'Várakozik jóváhagyásra'),
        ('approved', 'Jóváhagyva'),
        ('rejected', 'Elutasítva'),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('parent', 'child')
        verbose_name = 'Szülő-gyerek kapcsolat'
        verbose_name_plural = 'Szülő-gyerek kapcsolatok'

    def __str__(self):
        return f'{self.parent.username} -> {self.child.username}'

    def approve(self):
        """Jóváhagyja a kapcsolatot"""
        self.status = 'approved'
        self.approved_at = timezone.now()
        self.save()

class UserRole(models.Model):
    """
    Felhasználó szerepkör kapcsolat - ez a fő modell a szerepkörök kezelésére
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    sport = models.ForeignKey(Sport, on_delete=models.CASCADE)

    # Edző kapcsolat (csak sportoló vagy szülő szerepkörnél szükséges)
    coach = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='athletes',
        help_text="A sportoló vagy szülőhöz rendelt edző"
    )

    # Szülő kapcsolat (csak sportoló szerepkörnél szükséges, ha kiskorú)
    parent = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="userrole_children",
        help_text="A sportoló szülője (ha kiskorú)"
    )

    # Jóváhagyási státusz
    STATUS_CHOICES = (
        ('pending', 'Várakozik jóváhagyásra'),
        ('approved', 'Jóváhagyva'),
        ('rejected', 'Elutasítva'),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    # Külön flag-ek részleges jóváhagyás követésére
    approved_by_parent = models.BooleanField(default=False)
    approved_by_coach = models.BooleanField(default=False)

    # Ki hagyta jóvá és mikor
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_roles',
        help_text="Ki hagyta véglegesen jóvá ezt a szerepkört"
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # Létrehozás időpontja
    created_at = models.DateTimeField(auto_now_add=True)

    # Megjegyzések
    notes = models.TextField(blank=True, help_text="Megjegyzések a szerepkörhöz")

    class Meta:
        unique_together = ('user', 'role', 'club', 'sport', 'coach', 'parent')
        verbose_name = 'Felhasználó szerepkör'
        verbose_name_plural = 'Felhasználó szerepkörök'
        ordering = ['-created_at']

    def __str__(self):
        coach_info = f" (Edző: {self.coach.username})" if self.coach else ""
        parent_info = f" (Szülő: {self.parent.username})" if self.parent else ""
        return f'{self.user.username} - {self.role.name} @ {self.club.short_name}/{self.sport.name}{coach_info}{parent_info}'

    # --- Jóváhagyás logika ---
    def approve_by_parent(self, parent_user):
        """Szülő jóváhagyása"""
        if self.parent == parent_user:
            self.approved_by_parent = True
            self._try_finalize_approval(parent_user)

    def approve_by_coach(self, coach_user):
        """Edző jóváhagyása"""
        if self.coach == coach_user:
            self.approved_by_coach = True
            self._try_finalize_approval(coach_user)

    def _try_finalize_approval(self, approver):
        """
        Ha minden szükséges fél jóváhagyta, véglegesíti az approval-t.
        """
        if self.role.name == "Sportoló":
            if self.user.profile.is_adult:
                # 18 feletti sportolónál csak edző kell
                if self.approved_by_coach:
                    self._finalize(approver)
            else:
                # 18 alatti sportolónál szülő + edző
                if self.approved_by_coach and self.approved_by_parent:
                    self._finalize(approver)
        elif self.role.name == "Szülő":
            # Szülőt az edző hagyja jóvá
            if self.approved_by_coach:
                self._finalize(approver)
        else:
            # Edzőt vagy vezetőt csak a klubvezető hagyhatja jóvá
            if self.status == "pending":
                self._finalize(approver)

    def _finalize(self, approver):
        """Végleges jóváhagyás"""
        self.status = "approved"
        self.approved_by = approver
        self.approved_at = timezone.now()
        self.save(update_fields=['status', 'approved_by', 'approved_at',
                                 'approved_by_coach', 'approved_by_parent'])

    def reject(self, rejected_by_user):
        """Elutasítja a szerepkört"""
        self.status = 'rejected'
        self.approved_by = rejected_by_user
        self.approved_at = timezone.now()
        self.save(update_fields=['status', 'approved_by', 'approved_at'])

    @property
    def needs_approval_from(self):
        """
        Megadja, hogy kinek kell még jóváhagynia ezt a szerepkör-igénylést.
        """
        # Ha a státusz már Approved vagy Rejected, nincs szükség további jóváhagyásra.
        if self.status == 'approved' or self.status == 'rejected':
            return None

        # Egyesületi vezető szerepkör
        # A klubvezetői szerepkör igényét nem kell jóváhagyni (csak egy adminnak kell esetleg).
        if self.role.name == 'Egyesületi vezető':
            return None

        # Edző és Szülő szerepkör
        # Ezeket az egyesület vezetője hagyja jóvá.
        if self.role.name == 'Edző' or self.role.name == 'Szülő':
            try:
                leader_role = UserRole.objects.get(
                    club=self.club,
                    role__name='Egyesületi vezető',
                    status='approved'
                )
                return leader_role.user
            except UserRole.DoesNotExist:
                return None

        # Sportoló szerepkör (ez a legösszetettebb)
        if self.role.name == 'Sportoló':
            if self.user.is_adult:
                # Ha felnőtt, akkor az Edzőnek kell jóváhagynia, ha van kijelölt edző.
                return self.coach if self.coach else None
            else:
                # Ha kiskorú, a jóváhagyási lánc: Szülő -> Edző
                if not self.parent:
                    # Nincs szülő megadva, nem jóváhagyható
                    return None
                
                # Ha a szülő még nem hagyta jóvá, a szülő az, akinek jóvá kell hagynia
                if self.status == 'pending' and self.parent_id and not self.approved_by_parent:
                    return self.parent
                
                # Ha a szülő már jóváhagyta, akkor az edzőnek kell jóváhagynia
                if self.approved_by_parent and not self.approved_by_coach:
                    return self.coach
                
                # Mindenki jóváhagyta (szülő és edző is)
                return None
        
        return None

    @property
    def auto_approve(self):
        """Megadja, hogy automatikusan jóvá kell-e hagyni"""
        return self.role.name == 'Egyesületi vezető'