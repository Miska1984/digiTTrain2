from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.conf import settings
from django.db.models import Q
from users.models import UserRole # <<< Feltételezett import a szerepkörökhöz

# Lekérjük a custom User modellt
User = get_user_model()

# A TopUpForm-ban a minimális feltöltési összeget definiáljuk.
MIN_TOPUP_AMOUNT_FT = 1500

# ----------------------------------------------------------------------
# SEGÉD LOGIKA a Szerepkör alapú felhasználólekérdezéshez
# ----------------------------------------------------------------------

def _is_role(user, role_name):
    """Ellenőrzi, hogy a felhasználónak van-e elfogadott szerepköre."""
    if not user.is_authenticated:
        return False
    # A users/utils.py-ban látott logika alapján
    return user.user_roles.filter(role__name=role_name, status="approved").exists()

def get_related_athletes_or_children(user):
    """
    Lekéri a Szülőhöz tartozó Gyermekeket vagy az Edző/Vezetőhöz tartozó Sportolókat.
    """
    # ------------------------------------------------------------------
    # 1. Edző/Vezető Logika (ez jól működik)
    # ------------------------------------------------------------------
    if _is_role(user, 'Edző') or _is_role(user, 'Egyesületi Vezető'):
        
        active_roles = UserRole.objects.filter(
            user=user,
            role__name__in=['Edző', 'Egyesületi Vezető'],
            status='approved'
        ).values('club_id', 'sport_id').distinct()

        q_filter = Q()
        for role_data in active_roles:
            q_filter |= Q(
                user_roles__role__name='Sportoló',
                user_roles__status='approved',
                user_roles__club_id=role_data['club_id'],
                user_roles__sport_id=role_data['sport_id']
            )
        
        return User.objects.filter(q_filter).distinct()
        
    # ------------------------------------------------------------------
    # 2. Szülő Logika (JAVÍTVA)
    # ------------------------------------------------------------------
    elif _is_role(user, 'Szülő'):
        
        # 🚨 FIX: Ezt a részt kell a valós modellkapcsolatra cserélni!
        # Feltételezve, hogy a User modellen van egy reverse relation a gyermekekre, 
        # melynek neve pl. 'gyermekei'.
        try:
            # PÉLDA: user.gyermekei.all()
            # KÉREM, ELLENŐRIZZE ÉS CSERÉLJE LE a 'gyermekei' részt a valós reverse relation nevére!
            return user.gyermekei.all() 
        except AttributeError:
            # Ha nem sikerült, a felhasználó csak magát tudja választani (ami a default).
            print(f"HIBA: A Szülő-Gyermek kapcsolat ({user}.gyermekei.all()) nem található!")
            return User.objects.none()

    return User.objects.none()

# ----------------------------------------------------------------------
# 1. Credit Feltöltés Űrlap (TopUpForm)
# ----------------------------------------------------------------------

class TopUpForm(forms.Form):
    """
    Űrlap a Credit feltöltés összegének megadásához, 
    a számlázási adatok bekéréséhez és a célfelhasználó kiválasztásához.
    """
    
    # 1. Összeg és Célfelhasználó
    amount_ft = forms.DecimalField(
        label="Feltöltendő összeg (Ft)",
        max_digits=10,
        decimal_places=0, 
        validators=[MinValueValidator(MIN_TOPUP_AMOUNT_FT)],
        widget=forms.NumberInput(attrs={'min': MIN_TOPUP_AMOUNT_FT, 'step': 1000, 'placeholder': 'Minimum 1500 Ft'}),
        help_text=f'Minimum feltöltési összeg: {MIN_TOPUP_AMOUNT_FT} Ft.'
    )

    # A célfelhasználó ModelChoiceField segítségével.
    target_user = forms.ModelChoiceField(
        queryset=User.objects.none(),  
        label="Jóváírás Személye", 
        empty_label="Válassza ki, ki kapja a Creditet",
        help_text="Akár saját magának, akár egy alárendeltjének tölt fel Creditet."
    )

    # 2. Számlázási adatok
    billing_name = forms.CharField(label="Számlázási Név (Cég vagy magánszemély)", max_length=255)
    billing_address = forms.CharField(label="Számlázási Cím", widget=forms.Textarea(attrs={'rows': 2}))
    tax_number = forms.CharField(label="Adószám (opcionális)", max_length=50, required=False, help_text="Ha cégnévre kéri a számlát.")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        
        # Kidobjuk a már nem használt argumentumot
        if 'target_user_queryset' in kwargs:
             kwargs.pop('target_user_queryset') 
        
        super().__init__(*args, **kwargs)

        # ------------------------------------------------------------------
        # Dinamikus Szűrési Logika a target_user mezőhöz (PK-alapú QuerySet Union)
        # ------------------------------------------------------------------
        if self.user and self.user.is_authenticated:
            
            # 1. PK-k gyűjtése: Kezdünk a saját felhasználó PK-jával
            allowed_pks = {self.user.pk}
            
            # 2. Szerepkör alapú ellenőrzés
            is_athlete = _is_role(self.user, 'Sportoló')
            is_parent_or_coach = _is_role(self.user, 'Szülő') or _is_role(self.user, 'Edző') or _is_role(self.user, 'Egyesületi Vezető')
            
            if is_athlete:
                # Sportoló: Csak saját maga.
                pass 
            
            elif is_parent_or_coach:
                # Szülő, Edző/Vezető: Saját maga ÉS az alárendeltek
                related_users_queryset = get_related_athletes_or_children(self.user)
                
                # Hozzáadjuk a kapcsolódó felhasználók PK-jait a halmazhoz
                allowed_pks.update(related_users_queryset.values_list('pk', flat=True))
            
            # 3. Létrehozzuk a végső QuerySet-et a kombinált PK-k alapján
            allowed_users_queryset = User.objects.filter(pk__in=list(allowed_pks)).order_by('username')
            
            # 4. Beállítjuk a target_user opcióit
            self.fields['target_user'].queryset = allowed_users_queryset
            
            # 5. Kezeljük a Sportolók esetét vagy az egyetlen választható felhasználót
            if allowed_users_queryset.count() <= 1:
                # Beállítjuk az initial értéket (önmaga), és letiltjuk a választási lehetőséget
                self.fields['target_user'].initial = self.user.pk
                self.fields['target_user'].widget.attrs['disabled'] = True
            
            # Ha több opció van, saját magát állítjuk be alapértelmezettnek (kezdőérték)
            else:
                 self.fields['target_user'].initial = self.user.pk
        
            # 6. Kitöltjük az alapértelmezett számlázási adatokat
            self.fields['billing_name'].initial = self.user.get_full_name() or self.user.username


# ----------------------------------------------------------------------
# 2. Hirdetésmentes előfizetés (AdFreeToggleForm)
# ----------------------------------------------------------------------

class AdFreeToggleForm(forms.Form):
    """
    Egyszerű űrlap a hirdetésmentes előfizetés aktiválásához/megújításához.
    """
    plan_id = forms.IntegerField(
        widget=forms.HiddenInput(),
        required=False
    )