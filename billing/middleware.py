# billing/middleware.py

from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from .context_processors import ad_free_status


class InterstitialAdMiddleware(MiddlewareMixin):

    REQUEST_COUNTER_KEY = 'ad_interstitial_count'
    REQUEST_LIMIT = 3
    AD_COOLDOWN_SECONDS = 180   # 3 perc hírdetés védelmi idő

    EXCLUDE_PREFIXES = [
        '/admin/',
        '/static/',
        '/media/',
        '/billing/ad-for-credit/',
        '/data-sharing/toggle/',
        '/billing/toggle-ad-free/',
        '/billing/run-algorithm/',
        '/login/',
        '/logout/',
        '/register/',
        '/users/login/',
        '/users/logout/',
        '/users/register/',
    ]

    def should_skip(self, request):
        path = request.path.lower()

        # 1) Globális kizárások
        for prefix in self.EXCLUDE_PREFIXES:
            if path.startswith(prefix):
                return True
        
        # AJAX (fetch/XMLHttpRequest) kérések felismerése
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return True
        #

        # 2) AJAX automatikus kizárás
        if '/ajax/' in path:
            return True

        # 3) API-szerű végpontok kizárása
        if path.endswith('/json') or path.endswith('.json'):
            return True

        # 4) Nem bejelentkezett felhasználó
        if not request.user.is_authenticated:
            return True

        # 5) Ha a felhasználó hirdetésmentes
        is_ad_free = ad_free_status(request)['is_ad_free']
        if is_ad_free:
            return True

        return False

    def process_request(self, request):

        if self.should_skip(request):
            return None

        # ⏳ 6) Hírdetés cooldown (180 mp)
        last_ad_time = request.session.get('last_ad_time')

        if last_ad_time:
            last_ad_time = timezone.datetime.fromisoformat(last_ad_time)
            elapsed = (timezone.now() - last_ad_time).total_seconds()

            if elapsed < self.AD_COOLDOWN_SECONDS:
                # Még tart a védelmi idő → soha nem mutatunk hirdetést
                return None

        # 🔢 7) Kérés számláló
        current_count = request.session.get(self.REQUEST_COUNTER_KEY, 0) + 1
        request.session[self.REQUEST_COUNTER_KEY] = current_count

        # 🎯 Cél elérve: mutatjuk a hirdetést
        if current_count >= self.REQUEST_LIMIT:
            request.session[self.REQUEST_COUNTER_KEY] = 0
            request.session['last_ad_time'] = timezone.now().isoformat()  # hírdetés ideje
            return render(request, 'billing/interstitial_ad.html')

        return None
