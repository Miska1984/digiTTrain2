from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.conf import settings

# Lekérjük a custom User modellt
User = get_user_model()

# A TopUpForm-ban a minimális feltöltési összeget definiáljuk.
MIN_TOPUP_AMOUNT_FT = 1500

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
        decimal_places=0, # Egész Ft-ban gondolkodunk
        validators=[MinValueValidator(MIN_TOPUP_AMOUNT_FT)],
        widget=forms.NumberInput(attrs={'min': MIN_TOPUP_AMOUNT_FT, 'step': 1000, 'placeholder': 'Minimum 1500 Ft'}),
        help_text=f'Minimum feltöltési összeg: {MIN_TOPUP_AMOUNT_FT} Ft.'
    )

    # A célfelhasználó ModelChoiceField segítségével.
    # Ez dinamikusan töltődik a views.py-ban átadott queryset-ből.
    target_user = forms.ModelChoiceField(
        queryset=User.objects.none(),  # Ezt a konstruktorban felülírjuk
        label="Jóváírás Célja",
        empty_label="Válassza ki, ki kapja a Creditet",
        help_text="Akár saját magának, akár egy sportolónak tölt fel Creditet."
    )

    # 2. Számlázási adatok
    billing_name = forms.CharField(
        label="Számlázási Név (Cég vagy magánszemély)",
        max_length=255,
    )
    
    billing_address = forms.CharField(
        label="Számlázási Cím",
        widget=forms.Textarea(attrs={'rows': 2}),
    )
    
    tax_number = forms.CharField(
        label="Adószám (opcionális)",
        max_length=50,
        required=False,
        help_text="Ha cégnévre kéri a számlát."
    )

    # A __init__ metódussal felülírjuk a target_user queryset-jét
    def __init__(self, *args, **kwargs):
        # Az átadott 'user' és 'target_user_queryset' argumentumokat kezeljük
        self.user = kwargs.pop('user', None)
        target_user_queryset = kwargs.pop('target_user_queryset', User.objects.none())
        
        super().__init__(*args, **kwargs)

        # Beállítjuk a célfelhasználó opciókat
        self.fields['target_user'].queryset = target_user_queryset
        
        # Ha a felhasználó létezik, kitöltjük az alapértelmezett számlázási adatokat
        # (Feltételezzük, hogy a User modellhez van egy kapcsolódó Profile vagy Billing modell)
        if self.user and self.user.is_authenticated:
            # Most csak a felhasználó nevét állítjuk be alapértelmezettnek
            self.fields['billing_name'].initial = self.user.get_full_name() or self.user.username
            
            # Alapértelmezett célfelhasználó beállítása saját magára
            self.fields['target_user'].initial = self.user
            
            # Készíthetünk egy szűrőt is, hogy csak a saját sportolók jelenjenek meg, de 
            # a `target_user_queryset` már ezt a szűrést tartalmazhatja a View-ból.


# ----------------------------------------------------------------------
# 2. Hirdetésmentes előfizetés (AdFreeToggleForm)
# ----------------------------------------------------------------------

class AdFreeToggleForm(forms.Form):
    """
    Egyszerű űrlap a hirdetésmentes előfizetés aktiválásához/megújításához.
    Csak POST kérésekhez van használva a views.py-ban.
    """
    # A logikához nem feltétlenül kell mező, de adunk egy hidden mezőt a csomag ID-nak
    # (bár a views.py jelenleg a név alapján keres)
    plan_id = forms.IntegerField(
        widget=forms.HiddenInput(),
        required=False
    )