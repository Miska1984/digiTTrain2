# billing/decorators.py
from django.shortcuts import redirect, render
from django.contrib import messages
from functools import wraps
from .utils import has_active_subscription

def subscription_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # 1. Bejelentkezés ellenőrzése
        if not request.user.is_authenticated:
            return redirect("users:login")

        # 2. Specifikus ML előfizetés ellenőrzése a központi utils segítségével
        if not has_active_subscription(request.user, 'ML_ACCESS'):
            # Itt eldöntheted, hová küldöd: egy általános oldalra, vagy az ML-specifikus "locked" oldalra
            return render(request, "ml_engine/dashboard_locked.html", {
                "has_subscription": False
            })

        return view_func(request, *args, **kwargs)
    return _wrapped_view