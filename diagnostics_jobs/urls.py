# diagnostics_jobs/urls.py
from django.urls import path
from . import api
from . import views

app_name = "diagnostics_jobs"

urlpatterns = [
    path("create/", api.create_diagnostic_job, name="create_diagnostic_job"),
    path("<int:job_id>/status/", api.get_job_status, name="get_job_status"),
    path("<int:job_id>/result/", api.get_job_result, name="get_job_result"),
    path("cleanup/", api.cleanup_old_videos, name="cleanup_old_videos"),
    path("run-job/", views.run_job_view, name="run_job"),

    # Profil adatok megtekintése/szerkesztése (GET/POST a formhoz)
    path("profile/anthropometry/", views.anthropometry_profile_view, name="anthropometry_profile_view"),
    
    # 🆕 ÚJ ÚTVONAL: Videó feltöltés indítása (AJAX POST)
    path("profile/anthropometry/upload/", views.upload_anthropometry_video, name="upload_anthropometry_video"),

    # ❗ Megjegyzés: A 'user_id' alapú API endpoint már a meglévő kódban volt, ez maradhat.
    path("<int:user_id>/anthropometry/", api.anthropometry_profile, name="anthropometry_profile"),

    # 🆕 Kalibrációs végpont
    path('calibrate-photos/', views.calibrate_anthropometry_api, name='calibrate_anthropometry_with_photos'),
]

