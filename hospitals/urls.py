# hospitals/urls.py
from django.urls import path
from . import views
from donors import views as donor_views

urlpatterns = [
    # Dashboard
    path('dashboard/', views.hospital_dashboard, name='hospital_dashboard'),
    
    # Blood Requests
    path('emergency/', views.create_blood_request, name='create_blood_request'),
    path('requests/', views.all_blood_requests, name='all_blood_requests'),
    path('request/<int:request_id>/', views.view_blood_request, name='view_blood_request'),
    path('request/<int:request_id>/fulfill/', views.mark_fulfilled, name='mark_fulfilled'),
    path('request/<int:request_id>/cancel/', views.cancel_request, name='cancel_request'),
    
    # Donor Management (LIMITED ACCESS)
    path('donors/', views.hospital_donors, name='hospital_donors'),
    # Donor detail view for hospitals (limited info)
    path('donor/<int:donor_id>/', donor_views.view_donor_detail, name='view_donor_detail'),
    # notify_donor remains available in views but is intentionally not exposed as public URL in some setups
    
    # Profile Management
    path('profile/', views.hospital_profile, name='hospital_profile'),
    path('profile/edit/', views.edit_hospital_profile, name='edit_hospital_profile'),
]