# diagnostics/forms.py
from django import forms

class GeneralDiagnosticUploadForm(forms.Form):
    """
    Videófeltöltő űrlap az általános (gépi látás) elemzéshez.
    """
    video = forms.FileField(
        label="Videó feltöltése",
        help_text="Töltsd fel a teljes alakos, jól megvilágított videót (MP4 formátumban).",
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': 'video/mp4'
        })
    )

    notes = forms.CharField(
        label="Megjegyzés (opcionális)",
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Ha van külön megjegyzésed a videóval kapcsolatban, ide írhatod.'
        })
    )

class GeneralDiagnosticUploadForm(forms.Form):
    """
    Videófeltöltő űrlap az általános (gépi látás) elemzéshez.
    """
    video = forms.FileField(
        label="Videó feltöltése",
        help_text="Töltsd fel a teljes alakos, jól megvilágított videót (MP4 formátumban).",
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': 'video/mp4'
        })
    )

    notes = forms.CharField(
        label="Megjegyzés (opcionális)",
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Ha van külön megjegyzésed a videóval kapcsolatban, ide írhatod.'
        })
    )

    