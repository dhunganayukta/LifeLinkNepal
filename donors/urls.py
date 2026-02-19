# donors/urls.py - CORRECTED VERSION

from django.urls import path
from donors import views

urlpatterns = [
    # Dashboard
    path('dashboard/', views.donor_dashboard, name='donor_dashboard'),
    
    # Profile
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    
    # Donation History
    path('history/', views.donation_history, name='donation_history'),
    
    # Availability
    path('availability/toggle/', views.update_availability, name='update_availability'),
    
    # Find Hospitals
    path('hospitals/nearby/', views.find_nearby_hospitals, name='find_nearby_hospitals'),
    
    # Notifications - NEW WORKFLOW
    path('notification/<int:notification_id>/', views.view_notification_detail, name='view_notification_detail'),
    path('notification/<int:notification_id>/accept/', views.accept_blood_request, name='accept_blood_request'),
       # OLD ENDPOINTS - Keep for backward compatibility
    path('request/<int:request_id>/decline/', views.reject_blood_request, name='reject_blood_request'),
 
   
    
    # Notifications - Mark as read
    path('notification/<int:notification_id>/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    
    # Blood Requests - View details
    path('request/<int:request_id>/', views.view_blood_request_detail, name='view_blood_request_detail'),
   
]