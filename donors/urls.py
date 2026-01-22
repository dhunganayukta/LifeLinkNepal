# donors/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('dashboard/', views.donor_dashboard, name='donor_dashboard'),
    
    # Profile Management
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    
    # Blood Requests
    path('request/<int:request_id>/', views.view_blood_request_detail, name='view_blood_request_detail'),
    path('request/<int:request_id>/accept/', views.accept_blood_request, name='accept_blood_request'),
    path('request/<int:request_id>/decline/', views.decline_blood_request, name='decline_blood_request'),
    
    # Nearby Hospitals
    path('hospitals/nearby/', views.find_nearby_hospitals, name='find_nearby_hospitals'),
    
    # Availability
    path('availability/toggle/', views.update_availability, name='update_availability'),
    
    # Notifications
    path('notification/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/read-all/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    
    # Donation History
    path('history/', views.donation_history, name='donation_history'),
]