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
]
