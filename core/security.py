# core/security.py
"""
Központi biztonsági helper függvények
Használat: from core.security import PermissionChecker
"""

from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from users.models import UserRole


class PermissionChecker:
    """Központi jogosultság ellenőrző osztály"""
    
    @staticmethod
    def get_athlete_job_or_403(job_model, request, job_id):
        """
        Lekér egy DiagnosticJob-ot ÉS ellenőrzi, hogy a user-é (profile kapcsolaton keresztül).
        
        Args:
            job_model: DiagnosticJob model osztály
            request: Django request objektum
            job_id: A job ID-ja
            
        Returns:
            job: A DiagnosticJob objektum
            
        Raises:
            Http404: Ha nem létezik
            PermissionDenied: Ha nem a user-é
        """
        job = get_object_or_404(job_model, id=job_id)
        
        # Ellenőrizd, hogy a job profilja a current user-é
        if job.profile.athlete != request.user:
            raise PermissionDenied("Nincs jogosultságod ehhez a diagnosztikai feladathoz!")
        
        return job
    
    @staticmethod
    def get_coach_clubs(request):
        """
        Visszaadja azokat a klubokat, ahol a user coach szerepkörben approved státuszban van.
        
        Args:
            request: Django request objektum
            
        Returns:
            QuerySet: Club ID-k listája
        """
        return UserRole.objects.filter(
            user=request.user,
            role__name='coach',
            status='approved'
        ).values_list('club', flat=True)
    
    @staticmethod
    def get_coach_session_or_403(session_model, request, session_id):
        """
        Lekér egy TrainingSession-t ÉS ellenőrzi, hogy a coach klubjához tartozik-e.
        
        Args:
            session_model: TrainingSession model osztály
            request: Django request objektum
            session_id: A session ID-ja
            
        Returns:
            session: A TrainingSession objektum
            
        Raises:
            Http404: Ha nem létezik
            PermissionDenied: Ha nem a coach klubjához tartozik
        """
        coach_clubs = PermissionChecker.get_coach_clubs(request)
        
        session = get_object_or_404(session_model, id=session_id)
        
        # Ellenőrizd, hogy a session klubja benne van-e a coach klubjaiban
        if session.club.id not in coach_clubs:
            raise PermissionDenied("Nincs jogosultságod ehhez az edzéshez!")
        
        return session