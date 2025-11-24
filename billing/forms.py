# billing/forms.py
from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from .models import SubscriptionPlan, JobPrice

User = get_user_model()

# ==============================================================================
# 1. HIRDETÉSMENTESSÉG VÁSÁRLÁS FORM
# ==============================================================================

class AdFreeSubscriptionForm(forms.Form):
    """Hirdetésmentes előfizetési csomag vásárlása"""
    
    plan = forms.ModelChoiceField(
        queryset=SubscriptionPlan.objects.filter(is_ad_free=True).order_by('duration_days'),
        label="Válasszon csomagot",
        empty_label="--- Válasszon ---",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    billing_name = forms.CharField(
        max_length=255, 
        label="Számlázási Név",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    billing_address = forms.CharField(
        label="Számlázási Cím",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    
    tax_number = forms.CharField(
        max_length=50, 
        required=False, 
        label="Adószám (opcionális)",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    billing_email = forms.EmailField(
        label="Számlázási E-mail",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            self.fields['billing_name'].initial = self.user.get_full_name() or self.user.username
            self.fields['billing_email'].initial = self.user.email


# ==============================================================================
# 2. ELEMZÉSI CSOMAG VÁSÁRLÁS FORM
# ==============================================================================

class AnalysisPackagePurchaseForm(forms.Form):
    """Elemzési csomag vásárlása (darabszám alapú)"""
    
    package = forms.ModelChoiceField(
        queryset=JobPrice.objects.all().order_by('price_ft'),
        label="Válasszon elemzési csomagot",
        empty_label="--- Válasszon ---",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    billing_name = forms.CharField(
        max_length=255, 
        label="Számlázási Név",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    billing_address = forms.CharField(
        label="Számlázási Cím",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    
    tax_number = forms.CharField(
        max_length=50, 
        required=False, 
        label="Adószám (opcionális)",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    billing_email = forms.EmailField(
        label="Számlázási E-mail",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            self.fields['billing_name'].initial = self.user.get_full_name() or self.user.username
            self.fields['billing_email'].initial = self.user.email


# ==============================================================================
# 3. KOMBINÁLT SZÁMLÁZÁSI FORM (Előfizetés VAGY Elemzési csomag)
# ==============================================================================

class CombinedPurchaseForm(forms.Form): # ⬅️ A helyes osztálynév a view-ban használt alapján
    
    PURCHASE_CHOICES = [
        ('AD_FREE', 'Hirdetésmentes Előfizetés'),
        ('ANALYSIS_PACKAGE', 'Elemzési Csomag Vásárlása'),
    ]
    
    purchase_type = forms.ChoiceField(
        choices=PURCHASE_CHOICES,
        label="Vásárlás Típusa",
        widget=forms.RadioSelect
    )
    
    # ------------------ 1. Elemzési Csomag (AnalysisPackage/JobPrice) ------------------
    analysis_package = forms.ModelChoiceField(
        queryset=JobPrice.objects.none(), # Ezt majd a __init__ állítja be
        label="Válasszon Elemzési Csomagot",
        required=False,
        empty_label="--- Válasszon ---",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # ------------------ 2. Hirdetésmentes Csomag (SubscriptionPlan) ------------------
    subscription_plan = forms.ModelChoiceField(
        queryset=SubscriptionPlan.objects.none(), # Ezt majd a __init__ állítja be
        label="Válasszon Hirdetésmentes Csomagot",
        required=False,
        empty_label="--- Válasszon ---",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # Elemzési csomaghoz
    analysis_package = forms.ModelChoiceField(
        queryset=JobPrice.objects.none(), # EZ MARADJON!
        label="Válasszon Elemzési Csomagot",
        required=False,
        empty_label="--- Válasszon ---",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # Közös számlázási mezők
    billing_name = forms.CharField(
        max_length=255, 
        label="Számlázási Név",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    billing_address = forms.CharField(
        label="Számlázási Cím",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    
    tax_number = forms.CharField(
        max_length=50, 
        required=False, 
        label="Adószám",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    billing_email = forms.EmailField(
        label="Számlázási E-mail",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        # A view-ból érkező custom kwargs-ek kiemelése
        self.user = kwargs.pop('user', None)
        analysis_packages = kwargs.pop('analysis_packages', JobPrice.objects.none())
        ad_free_plans = kwargs.pop('ad_free_plans', SubscriptionPlan.objects.none())
        super().__init__(*args, **kwargs)
        
        # QuerySet beállítása a dinamikus csomagokhoz
        self.fields['analysis_package'].queryset = analysis_packages
        self.fields['subscription_plan'].queryset = ad_free_plans

    def clean(self):
        cleaned_data = super().clean()
        purchase_type = cleaned_data.get('purchase_type')
        subscription_plan = cleaned_data.get('subscription_plan')
        analysis_package = cleaned_data.get('analysis_package')
        
        # Ellenőrzés: megfelelő csomag ki van-e választva
        if purchase_type == 'AD_FREE':
            if not subscription_plan:
                self.add_error('subscription_plan', 'Kérjük, válasszon hirdetésmentes csomagot!')
        elif purchase_type == 'ANALYSIS_PACKAGE': # ✅ JAVÍTVA: Használd az 'ANALYSIS_PACKAGE' kulcsot
            if not analysis_package:
                self.add_error('analysis_package', 'Kérjük, válasszon elemzési csomagot!')
        
        return cleaned_data

