from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView


app_name = 'accounts'

urlpatterns = [
    # Registration (JWT)
    path('register/', views.register, name='register'),
    path('register-page/', views.register_page, name='register_page'),

    # Login (JWT)
    path('login/', views.login, name='login'),
    path('login-page/', views.login_page, name='login_page'),

    # Token refresh
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Dashboards (JWT-protected)
    path('donor/dashboard/', views.donor_dashboard, name='donor_dashboard'),
    path('hospital/dashboard/', views.hospital_dashboard, name='hospital_dashboard'),

    path('login-page/', views.login_page, name='login_page'),   # template page
    path('logout/', views.logout_view, name='logout'), 
]
