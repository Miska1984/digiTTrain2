from django.urls import path
from .views import create_diagnostic_job, run_diagnostic_job_view

urlpatterns = [
    path("create/", create_diagnostic_job, name="create_diagnostic_job"),
    path("run-job/", run_diagnostic_job_view, name="run_diagnostic_job"),
]
