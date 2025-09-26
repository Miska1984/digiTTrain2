# data_sharing/sharing_views/parent.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from users.models import UserRole
from biometric_data.models import WeightData
from users.utils import has_role

@login_required
def parent_dashboard(request):
    parent = request.user
    if not has_role(parent, "Szülő"):
        messages.error(request, "Nincs szülői szerepköröd.")
        return redirect("core:main_page")

    # Gyerekek lekérdezése
    children_roles = UserRole.objects.filter(
        parent=parent,
        role__name="Sportoló",
        status="approved"
    ).select_related("user__profile")

    children_data = []
    for role in children_roles:
        weight_entries = WeightData.objects.filter(
            user=role.user
        ).order_by("workout_date")

        # Ha nincs adat, ne adjunk üres chartot
        if weight_entries.exists():
            chart_data = {
                "labels": [entry.workout_date.strftime("%Y-%m-%d") for entry in weight_entries],
                "weights": [float(entry.morning_weight) for entry in weight_entries],
            }
        else:
            chart_data = {"labels": [], "weights": []}

        children_data.append({
            "child": role.user,
            "profile": role.user.profile,
            "chart": chart_data,
        })

    context = {
        "children_data": children_data,
    }
    return render(request, "data_sharing/parent/dashboard.html", context)
