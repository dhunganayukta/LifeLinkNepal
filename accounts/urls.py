from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # Registration (JWT)
    path('register/', views.register, name='register'),

    # Login (JWT)
    path('login/', views.login, name='login'),

    # Token refresh
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Dashboards (JWT-protected)
    path('donor/dashboard/', views.donor_dashboard, name='donor_dashboard'),
    path('hospital/dashboard/', views.hospital_dashboard, name='hospital_dashboard'),
]
