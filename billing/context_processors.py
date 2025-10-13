# billing/context_processors.py

from .models import UserSubscription # <-- Ellenőrizze, hogy ez importálható-e!
from django.utils import timezone
from .models import SubscriptionPlan # <-- Ha a 'plan.is_ad_free' sort használja

def ad_free_status(request):
    """
    Globális kontextus processzor a felhasználó hirdetésmentes státuszának megállapításához.
    """
    if not request.user.is_authenticated:
        return {'is_ad_free': False}

    is_ad_free = False
    
    try:
        # 1. Ellenőrizzük az aktív hirdetésmentes előfizetést
        # A related_name='subscription' alapján érjük el a UserSubscription objektumot
        # VAGY: Lekérjük a UserSubscription objektumot, ha a related_name nem működik:
        subscription = UserSubscription.objects.get(
            user=request.user, 
            end_date__gt=timezone.now() 
        )
        
        # Mivel a UserSubscription-nek van egy plan mezője, ami egy SubscriptionPlan-re mutat:
        if subscription.plan and subscription.plan.is_ad_free:
             is_ad_free = True
             
    except UserSubscription.DoesNotExist:
        pass
    except AttributeError:
        # A request.user.subscription AttributeError-t dobhat, ha nincs beállítva related_name
        pass
    except Exception as e:
        # Ide jöhetne a logolás, ha valami más hiba lép fel (pl. az adatbázis kapcsolat miatt)
        # print(f"Hiba a context processorban: {e}")
        pass

    # 2. Adminok mindig hirdetésmentesek
    if request.user.is_superuser:
        is_ad_free = True
        
    return {
        'is_ad_free': is_ad_free
    }