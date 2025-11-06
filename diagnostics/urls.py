from django.urls import path
from .views import (
    # ... A fő (nem feltöltő) nézetek
    create_diagnostic_job,
    run_diagnostic_job_view,
    job_status,
    list_diagnostic_jobs,
    diagnostics_dashboard,
    sport_diagnostics_list,
    # upload_wrestling_video,  # ❌ TÖRÖLVE: Birkózás nézet
    get_signed_gcs_url,
)

# 🆕 Importáljuk az új, dedikált, moduláris feltöltő nézeteket
from .analysis_views.squat_views import upload_squat_video       # <-- DEDIKÁLT GUGGOLÁS VIEW
from .analysis_views.posture_views import upload_posture_video   # <-- DEDIKÁLT TESTTARTÁS VIEW
from .analysis_views.shoulder_circumduction_views import upload_shoulder_circumduction_video
from .analysis_views.vertical_jump_views import upload_vertical_jump_video

app_name = "diagnostics"

urlpatterns = [
    # API útvonalak
    path("create/", create_diagnostic_job, name="create_diagnostic_job"),
    path("run-job/", run_diagnostic_job_view, name="run_diagnostic_job"),
    path("job-status/<int:job_id>/", job_status, name="job_status"),
    path("list/", list_diagnostic_jobs, name="list_diagnostic_jobs"),

    # Dashboard/Lista útvonalak
    path("dashboard/", diagnostics_dashboard, name="diagnostics_dashboard"),
    path("athlete/", diagnostics_dashboard, name="athlete_diagnostics"),
    path("sports/", sport_diagnostics_list, name="sport_diagnostics_list"),

    # ❌ TÖRÖLVE: Birkózás feltöltés
    # path("upload/wrestling/", upload_wrestling_video, name="upload_wrestling_video"), 

    # 🆕 ÚJ ÚTVONALAK a felosztott általános elemzésekhez (amik most már specifikusak)
    path("upload/posture/", upload_posture_video, name="upload_posture_video"),
    path("upload/squat/", upload_squat_video, name="upload_squat_video"),
    path("upload/shoulder-circumduction/", upload_shoulder_circumduction_video, name="upload_shoulder_circumduction_video"),
    path('upload/vertical-jump/', upload_vertical_jump_video, name='upload_vertical_jump_video'),

    # 🆕 ÚJ ÚTVONAL a GCS feltöltés előkészítéséhez
    path("upload/gcs-sign/", get_signed_gcs_url, name="get_signed_gcs_url"),
]

