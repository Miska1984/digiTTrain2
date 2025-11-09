# diagnostics/forms.py

from django import forms

# ----------------------------------------------------
# 1. Testtartás Elemzés Űrlap
# ----------------------------------------------------
class PostureDiagnosticUploadForm(forms.Form):
    """
    Videófeltöltő űrlap a Testtartás Elemzéshez.
    """
    video = forms.FileField(
        label="Testtartás videó feltöltése",
        help_text="Töltsd fel a teljes alakos, szemből (frontális) felvett videót (MP4).",
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': 'video/mp4'
        })
    )

# ----------------------------------------------------
# 2. Guggolás Elemzés Űrlap
# ----------------------------------------------------
class SquatDiagnosticUploadForm(forms.Form):
    """
    Videófeltöltő űrlap a Guggolás Elemzéshez.
    """
    video = forms.FileField(
        label="Guggolás videó feltöltése",
        help_text="Töltsd fel az oldalnézetből (profilból) felvett, 3-5 ismétlést tartalmazó videót (MP4).",
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': 'video/mp4'
        })
    )

# ----------------------------------------------------
# 3. Vállkörzés Elemzés Űrlap
# ----------------------------------------------------
class ShoulderCircumductionUploadForm(forms.Form):
    """
    Videófeltöltő űrlap a Vállkörzés Elemzéshez.
    """
    video = forms.FileField(
        label="Vállkörzés videó feltöltése",
        help_text="Töltsd fel a frontális nézetből (szemből) felvett videót (MP4).",
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': 'video/mp4'
        })
    )

class VerticalJumpDiagnosticUploadForm(forms.Form):
    """
    Form a Helyből Magassági Ugrás elemzéshez. Csak a megjegyzést kezeli.
    """
    notes = forms.CharField(
        label='Megjegyzés (opcionális)',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3})
    )
    # A video_url mezőt NEM definiáljuk itt, mivel azt a JS küldi a POST kérés body-jában.

    # ❗ Fontos: ez a mező a JS-ből jön, a view-nak kell kezelnie a POST request-ből
    video_url = forms.CharField(required=False, widget=forms.HiddenInput) 

    # Hozzáadhatunk egy job_type mezőt is rejtett beviteli mezőként a view kényelme érdekében, 
    # de a _process_video_upload segédfüggvény ezt már kezeli.

# ----------------------------------------------------
# 5. Egy Lábon Állás Elemzés Űrlap (SLS)
# ----------------------------------------------------
class SlsUploadForm(forms.Form):
    """
    Form az Egy Lábon Állás elemzéshez. Csak a megjegyzést kezeli.
    """
    notes = forms.CharField(
        label='Megjegyzés (opcionális)',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}) # Hozzáadva a 'form-control' osztályt a bootstrap stílus miatt
    )