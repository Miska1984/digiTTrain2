# billing/context_processors.py
from .models import UserSubscription
from django.utils import timezone

def ad_free_status(request):
    is_ad_free = False 
    if not request.user.is_authenticated:
        return {'is_ad_free': is_ad_free}
    
    # Az új struktúra szerint: van-e aktív AD_FREE típusú előfizetése
    is_ad_free = UserSubscription.objects.filter(
        user=request.user, 
        sub_type='AD_FREE',
        expiry_date__gt=timezone.now()
    ).exists()
        
    return {'is_ad_free': is_ad_free}