from .models import UserSubscription
from django.utils import timezone

def ad_free_status(request):
    """
    Globális kontextus processzor a felhasználó hirdetésmentes státuszának megállapításához.
    """
    if not request.user.is_authenticated:
        # Alapértelmezésben, ha nincs bejelentkezve, NEM hirdetésmentes
        return {'is_ad_free': False}

    is_ad_free = False
    
    # 1. Ellenőrizzük az aktív hirdetésmentes előfizetést
    try:
        # A related_name='subscription' alapján érjük el a UserSubscription objektumot
        subscription = request.user.subscription
        
        # Ellenőrizzük, hogy aktív-e, nem járt-e le, és hogy a csomag hirdetésmentes-e
        if subscription.is_active and subscription.end_date > timezone.now() and subscription.plan.is_ad_free:
            is_ad_free = True
            
    except UserSubscription.DoesNotExist:
        # Nincs rögzített előfizetés
        pass
        
    except AttributeError:
        # Nincs subscription objektum, vagy plan (bár a plan ForeignKey null=True)
        pass

    # 2. Ellenőrizhetünk egy külön engedélyt is, pl. adminok mindig hirdetésmentesek
    if request.user.is_superuser:
        is_ad_free = True
        
    return {
        'is_ad_free': is_ad_free
    }