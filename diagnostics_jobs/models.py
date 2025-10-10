from django.db import models
from django.conf import settings


class DiagnosticJob(models.Model):
    class JobStatus(models.TextChoices):
        PENDING = 'PENDING', 'Feldolgozásra vár'
        PROCESSING = 'PROCESSING', 'Feldolgozás alatt'
        COMPLETED = 'COMPLETED', 'Befejezve'
        FAILED = 'FAILED', 'Hiba történt'

    class JobType(models.TextChoices):
        GENERAL = 'GENERAL', 'Általános diagnosztika'
        WRESTLING = 'WRESTLING', 'Birkózás specifikus diagnosztika'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    sport_type = models.CharField(max_length=50, verbose_name="Sportág")
    job_type = models.CharField(max_length=20, choices=JobType.choices, default=JobType.GENERAL)
    video_url = models.URLField(verbose_name="Videó elérési út (Cloud Storage)")
    status = models.CharField(max_length=20, choices=JobStatus.choices, default=JobStatus.PENDING)
    priority = models.PositiveIntegerField(default=1, help_text="Magasabb érték = előbbi feldolgozás")
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    result = models.JSONField(null=True, blank=True, help_text="Diagnosztikai eredmények (JSON)")
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Diagnosztikai feladat"
        verbose_name_plural = "Diagnosztikai feladatok"
        ordering = ['-created_at']

    def __str__(self):
        return f"#{self.id} - {self.user.username} ({self.get_status_display()})"

    def mark_as_processing(self):
        self.status = self.JobStatus.PROCESSING
        self.save(update_fields=['status', 'started_at'])

    def mark_as_completed(self, result_data: dict):
        self.status = self.JobStatus.COMPLETED
        self.result = result_data
        self.save(update_fields=['status', 'result', 'completed_at'])

    def mark_as_failed(self, error: str):
        self.status = self.JobStatus.FAILED
        self.error_message = error
        self.save(update_fields=['status', 'error_message'])
