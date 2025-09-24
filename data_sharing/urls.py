from django.urls import path
from . import views
from .sharing_views import parent, coach, leader

app_name = 'data_sharing'

urlpatterns = [
    # Közös megosztás nézetek
    path('', views.data_sharing_center, name='sharing_center'),
    path('toggle/', views.toggle_permission, name='toggle_permission'),
    path('shared/', views.shared_data_view, name='shared_data_view'),

    # Szülői nézetek
    path('parent/', parent.parent_dashboard, name='parent_dashboard'),
    path('parent/child/<int:child_id>/', parent.child_detail, name='child_detail'),

    # Edzői nézetek
    path('coach/', coach.coach_dashboard, name='coach_dashboard'),
    path('coach/athlete/<int:athlete_id>/', coach.athlete_detail, name='athlete_detail'),

    # Egyesületi vezetői nézetek
    path('leader/', leader.leader_dashboard, name='leader_dashboard'),
    path('leader/sport/<int:sport_id>/', leader.sport_detail, name='sport_detail'),

]
