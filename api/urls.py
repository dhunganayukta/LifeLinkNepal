# api/urls.py - COMPLETE URL CONFIGURATION

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router and register viewsets
router = DefaultRouter()
router.register(r'donors', views.DonorViewSet, basename='donor')
router.register(r'hospitals', views.HospitalViewSet, basename='hospital')
router.register(r'blood-requests', views.BloodRequestViewSet, basename='blood-request')

app_name = 'api'

urlpatterns = [
    # Router URLs
    path('', include(router.urls)),
    
    # Custom endpoints
    path('stats/', views.dashboard_stats, name='dashboard-stats'),
    path('leaderboard/', views.donor_leaderboard, name='donor-leaderboard'),
]

# Available endpoints:
# GET  /api/donors/                          - List all donors
# GET  /api/donors/{id}/                     - Get specific donor
# GET  /api/donors/{id}/donation_history/   - Get donor's donation history
# 
# GET  /api/hospitals/                       - List all hospitals
# GET  /api/hospitals/{id}/                  - Get specific hospital
# GET  /api/hospitals/{id}/blood_requests/  - Get hospital's blood requests
# 
# GET  /api/blood-requests/                  - List all blood requests
# GET  /api/blood-requests/{id}/             - Get specific request
# GET  /api/blood-requests/{id}/matched_donors/ - Get matched donors for request
# 
# GET  /api/stats/                           - Dashboard statistics
# GET  /api/leaderboard/                     - Top donors leaderboard