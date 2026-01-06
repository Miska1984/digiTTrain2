# billing/forms.py
from django import forms
from datetime import date
from .models import ServicePlan  # <--- JAVÍTVA: SubscriptionPlan helyett
from users.models import User

class UserFullNameChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        if hasattr(obj, 'profile'):
            # Magyar sorrend: Vezetéknév Keresztnév
            full_name = f"{obj.profile.first_name} {obj.profile.last_name}"
            
            # Életkor kiszámítása
            age_str = ""
            if obj.profile.date_of_birth:
                today = date.today()
                age = today.year - obj.profile.date_of_birth.year - (
                    (today.month, today.day) < (obj.profile.date_of_birth.month, obj.profile.date_of_birth.day)
                )
                age_str = f"({age} év)"

            # Sportág lekérése (Club -> sports mező)
            sport_str = ""
            # Megnézzük a sportoló szerepkörét
            role = obj.user_roles.filter(role__name='Sportoló').first()
            if role and role.club:
                # Mivel 'sports' mező van és valószínűleg ManyToMany, vesszővel elválasztva összefűzzük
                # Ha csak egyet akarsz, akkor a .first()-et használjuk
                first_sport = role.club.sports.first()
                if first_sport:
                    sport_str = f" - {first_sport.name}"

            return f"{full_name} {age_str}{sport_str}"
        
        return obj.get_full_name() or obj.username

class CombinedPurchaseForm(forms.Form):
    PURCHASE_CHOICES = [
        ('ANALYSIS', 'Elemzési csomag vásárlása'),
        ('AD_FREE', 'Hirdetésmentesség előfizetés'),
        ('ML_ACCESS', 'ML Funkciók elérése'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'Banki átutalás (Ft)'),
        ('CREDIT', 'Vásárlás Kreditpontokkal'),
    ]

    purchase_type = forms.ChoiceField(
        choices=PURCHASE_CHOICES, 
        widget=forms.RadioSelect,
        initial='ANALYSIS'
    )
    
    payment_method = forms.ChoiceField(
        choices=PAYMENT_METHOD_CHOICES,
        widget=forms.RadioSelect,
        initial='CASH'
    )

    target_user = UserFullNameChoiceField(
        queryset=User.objects.none(),
        label="Kedvezményezett kiválasztása",
        required=False,
        empty_label="Saját részemre",
        widget=forms.Select(attrs={'class': 'form-select mb-3', 'data-live-search': 'true'})
    )

    # Számlázási adatok (Csak CASH fizetésnél lesz kötelező a validációban)
    billing_name = forms.CharField(max_length=255, required=False, label="Számlázási név")
    billing_address = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False, label="Számlázási cím")
    billing_email = forms.EmailField(required=False, label="Számlázási e-mail")

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            from users.models import UserRole, Club
            from django.db.models import Q
            
            # 1. Lekérjük azokat a klubokat, ahol a user 'Egyesületi vezető'
            # A hibaüzenet szerint a helyes kulcsszó: userrole
            managed_clubs = Club.objects.filter(
                userrole__user=user,
                userrole__role__name='Egyesületi vezető',
                userrole__status='approved'
            )

            # 2. Szűrő a sportolókhoz
            q_filter = Q(role__name='Sportoló', status='approved')
            
            # Szülői vagy edzői kapcsolat
            user_filter = Q(parent=user) | Q(coach=user)
            
            # Egyesületi tagság (ha vezető)
            if managed_clubs.exists():
                user_filter |= Q(club__in=managed_clubs)
            
            # Lekérjük az ID-kat
            children_ids = UserRole.objects.filter(
                q_filter & user_filter
            ).values_list('user_id', flat=True).distinct()
            
            # User queryset beállítása
            self.fields['target_user'].queryset = User.objects.filter(
                id__in=children_ids
            ).select_related('profile')
            
            # Alapértelmezett választás beállítása
            if self.fields['target_user'].queryset.exists():
                # Ha csak egy van, válasszuk ki azt, ha több, maradjon az üres
                if self.fields['target_user'].queryset.count() == 1:
                    self.fields['target_user'].initial = self.fields['target_user'].queryset.first()

    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get("payment_method")
        billing_address = cleaned_data.get("billing_address")
        billing_name = cleaned_data.get("billing_name")

        # Ha banki utalást választott, de üresek a számlázási adatok
        if payment_method == 'CASH':
            if not billing_address:
                self.add_error('billing_address', "Banki utalás esetén a számlázási cím megadása kötelező!")
            if not billing_name:
                self.add_error('billing_name', "Banki utalás esetén a számlázási név megadása kötelező!")
        
        return cleaned_data
    
    