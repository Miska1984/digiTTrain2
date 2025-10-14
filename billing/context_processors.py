# billing/context_processors.py

from .models import UserSubscription
from django.utils import timezone
from django.db.models import Q # Ezt importálni kell!

def ad_free_status(request):
    
    # Alapértelmezett érték: NEM hirdetésmentes
    is_ad_free = False 
    
    # 1. Ellenőrzés: Be van-e jelentkezve?
    if not request.user.is_authenticated:
        return {'is_ad_free': is_ad_free} # is_ad_free = False
    
    # 2. Előfizetés ellenőrzése
    try:
        # Lekérdezzük azokat az aktív előfizetéseket, amelyek hirdetésmentes csomaghoz tartoznak
        # Feltételezzük: UserSubscription van User-hez és Plan-hez FK-val
        
        active_ad_free_subscription = UserSubscription.objects.filter(
            user=request.user, 
            end_date__gt=timezone.now(),
            # Megnézzük, hogy a csomag (plan) is hirdetésmentes-e
            plan__is_ad_free=True 
        ).exists() # Csak azt ellenőrizzük, hogy létezik-e ilyen bejegyzés
        
        if active_ad_free_subscription:
             is_ad_free = True
             
    except Exception as e:
        # Ha bármilyen hiba történik (pl. hiányzó plan mező, adatbázis hiba), akkor is marad: is_ad_free = False
        # Logolni lehet: print(f"Hiba a context processorban: {e}")
        pass

    # 3. Admin felülbírálat
    if request.user.is_superuser:
        is_ad_free = True
        
    return {
        'is_ad_free': is_ad_free
    }