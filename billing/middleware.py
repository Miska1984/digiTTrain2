# billing/middleware.py

from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from .context_processors import is_user_ad_free # Importáljuk a context processort

class InterstitialAdMiddleware(MiddlewareMixin):
    """
    Ez a middleware egy átmeneti (interstitial) hirdetési oldalt jelenít meg
    minden harmadik kérés után, HA a felhasználó NEM hirdetésmentes.
    
    FONTOS: Mivel a Google szigorúan tiltja a teljes képernyős hirdetések
    manuális/erőszakos megjelenítését, ez a megvalósítás ITT EGY BELSŐ,
    átmeneti sablont tölt be, ami a hirdetés kódját tartalmazza.
    """
    
    # 💥 FIGYELEM: Ez a számláló nagyon egyszerű!
    # Valódi alkalmazásban ezt a felhasználó Session-jében kell tárolni.
    # Most a demó kedvéért a Session-t használjuk.
    REQUEST_COUNTER_KEY = 'ad_interstitial_count'
    REQUEST_LIMIT = 3 # Minden 3. kérés után jelenjen meg

    # Azon útvonalak, amiket figyelmen kívül hagyunk (API hívások, statikus fájlok)
    EXCLUDE_PATHS = [
        '/admin/', '/static/', '/media/', '/billing/run-algorithm/', '/billing/ad-for-credit/'
    ]

    def process_request(self, request):
        # 1. Kizárások ellenőrzése
        for path in self.EXCLUDE_PATHS:
            if request.path.startswith(path):
                return None # Továbbengedjük a kérést
        
        # 2. Hirdetésmentes státusz ellenőrzése (Context Processorból)
        # Feltételezzük, hogy a context_processors.py által lekérhető a státusz
        is_ad_free = is_user_ad_free(request)['is_ad_free'] 
        
        if request.user.is_authenticated and not is_ad_free:
            
            # 3. Kérésszámláló kezelése a session-ben
            current_count = request.session.get(self.REQUEST_COUNTER_KEY, 0)
            current_count += 1
            request.session[self.REQUEST_COUNTER_KEY] = current_count

            # 4. Megjelenítési limit ellenőrzése
            if current_count >= self.REQUEST_LIMIT:
                # Visszaállítjuk a számlálót
                request.session[self.REQUEST_COUNTER_KEY] = 0 
                
                # Átmeneti oldal megjelenítése (Response visszaadása)
                # FONTOS: Mivel a render azonnal Response-t ad vissza, ez a hívás
                # megszakítja az eredeti nézet (view) futását.
                return render(request, 'billing/interstitial_ad.html', {})
                
        # Ha be van jelentkezve ÉS hirdetésmentes, vagy ha a számláló alatt van, folytatjuk.
        return None