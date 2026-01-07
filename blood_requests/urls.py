

from django.urls import path
from . import views
urlpatterns = [
    path('', views.blood_requests_home, name='requests_home'),  # Changed name
    path('emergency/', views.emergency, name='emergency'),
]