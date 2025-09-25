# data_sharing/sharing_views/parent.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from users.models import UserRole
from biometric_data.models import WeightData, HRVandSleepData, WorkoutFeedback, RunningPerformance
from users.utils import has_role

@login_required
def parent_dashboard(request):
    """
    Szülői dashboard – minden gyermek biometrikus adata egy helyen.
    """
    parent = request.user
    if not has_role(parent, "Szülő"):
        messages.error(request, "Nincs szülői szerepköröd.")
        return render(request, "data_sharing/access_denied.html")

    # A szülő gyermekei
    child_roles = UserRole.objects.filter(
        parent=parent,
        role__name="Sportoló",
        status="approved"
    ).select_related("user__profile", "sport", "club", "coach")

    # Szűrő (ha a szülő választ egy konkrét gyereket)
    selected_child_id = request.GET.get("child_id")
    if selected_child_id:
        child_roles = child_roles.filter(user__id=selected_child_id)

    # Gyermekek adatai + biometrikus adatok összegyűjtése
    children_data = []
    for role in child_roles:
        child = role.user

        weight_data = WeightData.objects.filter(user=child).order_by("-workout_date")[:5]
        hrv_sleep_data = HRVandSleepData.objects.filter(user=child).order_by("-recorded_at")[:5]
        feedback_data = WorkoutFeedback.objects.filter(user=child).order_by("-workout_date")[:5]
        running_data = RunningPerformance.objects.filter(user=child).order_by("-run_date")[:5]

        children_data.append({
            "role": role,
            "weight_data": weight_data,
            "hrv_sleep_data": hrv_sleep_data,
            "feedback_data": feedback_data,
            "running_data": running_data,
        })

    context = {
        "children_data": children_data,
        "child_roles": child_roles,  # szűrőhöz
        "selected_child_id": int(selected_child_id) if selected_child_id else None,
    }
    return render(request, "data_sharing/parent/dashboard.html", context)
