from django.urls import path
from .views import create_diagnostic_job, run_diagnostic_job_view, job_status, list_diagnostic_jobs, diagnostics_dashboard
from . import views

app_name = "diagnostics"

urlpatterns = [
    path("create/", create_diagnostic_job, name="create_diagnostic_job"),
    path("run-job/", run_diagnostic_job_view, name="run_diagnostic_job"),
    path("job-status/<int:job_id>/", job_status, name="job_status"),
    path("list/", list_diagnostic_jobs, name="list_diagnostic_jobs"),
    
    path("dashboard/", diagnostics_dashboard, name="diagnostics_dashboard"),
    
    path("athlete/", views.diagnostics_dashboard, name="athlete_diagnostics"),
    
    path("upload/general/", views.upload_general_video, name="upload_general_video"),
    path("upload/general/", views.upload_general_video, name="upload_general_video"),
]
