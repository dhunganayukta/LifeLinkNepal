from django.urls import path
from . import views
urlpatterns = [
    path('register/',views.hospital_register,name='hospital_register'),
    path('dashboard/',views.hospital_dashboard,name='hospital_dashboard'),
    path('complete/<int:request_id>/',views.complete_request,name='complete_request'),
    
]
