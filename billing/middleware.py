# billing/middleware.py

from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from .context_processors import ad_free_status # <-- A helyes függvénynevet importáljuk

class InterstitialAdMiddleware(MiddlewareMixin):
    """
    Ez a middleware egy átmeneti (interstitial) hirdetési oldalt jelenít meg
    minden N. kérés után, HA a felhasználó NEM hirdetésmentes.
    A számlálót a felhasználó session-jében tárolja.
    """
    
    REQUEST_COUNTER_KEY = 'ad_interstitial_count'
    REQUEST_LIMIT = 3 # Példa: minden 3. oldalbetöltésnél jelenik meg a hirdetés
    
    # Azon útvonalak, amiket figyelmen kívül hagyunk (pl. API hívások, statikus fájlok)
    EXCLUDE_PATHS = [
        '/admin/', 
        '/static/', 
        '/media/', 
        '/billing/run-algorithm/', 
        '/billing/ad-for-credit/',
        '/billing/toggle-ad-free/',
        # 💥 FONTOS KIZÁRÁSOK a bejelentkezési, regisztrációs és kilépési oldalakhoz
        '/users/login/',    # Kizárja a login oldalt (és az arra irányuló POST kérést)
        '/users/logout/',   # Kizárja a logout útvonalat
        '/users/register/', # Kizárja a regisztrációs oldalt
        '/logout/',         # Esetleges más logout útvonal
        '/login/',          # Esetleges más login útvonal (biztos, ami biztos)
        '/register/',       # Esetleges más regisztrációs útvonal
        '/main_page/',
        '/index/'
        '/users/roles/parent/get_sports_by_club/',
        '/users/roles/parent/get_coaches_by_club_and_sport/',
        '/users/roles/parent/',

    ]
    
    def process_request(self, request):
        
        # 1. Kizárások ellenőrzése (ne jelenjen meg admin oldalon, stb.)
        for path in self.EXCLUDE_PATHS:
            if request.path.startswith(path):
                return None 
        
        # 2. Hirdetésmentes státusz ellenőrzése
        # A ad_free_status(request) függvényt hívjuk meg (context_processors.py)
        is_ad_free = ad_free_status(request)['is_ad_free'] 
        
        # Csak akkor foglalkozunk a számlálással és a hirdetéssel, ha be van jelentkezve ÉS NEM hirdetésmentes
        if request.user.is_authenticated and not is_ad_free:
            
            # 3. Kérésszámláló kezelése a session-ben
            # Lekérjük a számlálót, alapértelmezett értéke 0, ha nincs még session-ben
            current_count = request.session.get(self.REQUEST_COUNTER_KEY, 0)
            current_count += 1
            # Visszaírjuk a növelt értéket a session-be
            request.session[self.REQUEST_COUNTER_KEY] = current_count
            
            # 4. Megjelenítési limit ellenőrzése
            if current_count >= self.REQUEST_LIMIT:
                
                # Visszaállítjuk a számlálót a hirdetés megjelenítése után
                request.session[self.REQUEST_COUNTER_KEY] = 0 
                
                # Átmeneti oldal megjelenítése (ez megszakítja az eredeti kérés feldolgozását!)
                return render(request, 'billing/interstitial_ad.html', {})
                
        # Ha a felhasználó hirdetésmentes, vagy nincs bejelentkezve, vagy a számláló alatt van, továbbengedjük.
        return None