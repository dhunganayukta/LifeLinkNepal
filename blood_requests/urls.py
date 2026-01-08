from django.urls import path
from . import views
urlpatterns = [
    path('emergency/',views.emergency_request,name='emergency_request'),
]