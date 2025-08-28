from django.urls import path
from . import views
from . import views as user_views

urlpatterns = [
    path('', user_views.index, name='index'),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
]