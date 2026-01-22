# hospitals/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('dashboard/', views.hospital_dashboard, name='hospital_dashboard'),
    
    # Blood Request Management
    path('create-request/', views.create_blood_request, name='create_blood_request'),
    path('requests/', views.all_blood_requests, name='all_blood_requests'),
    path('request/<int:request_id>/', views.view_blood_request, name='view_blood_request'),
    path('request/<int:request_id>/fulfill/', views.mark_fulfilled, name='mark_fulfilled'),
    path('request/<int:request_id>/cancel/', views.cancel_request, name='cancel_request'),
    
    # Donor Management
    path('donors/', views.hospital_donors, name='hospital_donors'),
    path('donor/<int:donor_id>/', views.view_donor_detail, name='view_donor_detail'),
    path('donor/<int:donor_id>/notify/', views.notify_donor, name='notify_donor'),
    
    # Profile
    path('profile/', views.hospital_profile, name='hospital_profile'),
    path('profile/edit/', views.edit_hospital_profile, name='edit_hospital_profile'),
]