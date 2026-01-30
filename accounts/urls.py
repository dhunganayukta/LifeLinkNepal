from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView

app_name = 'accounts'

urlpatterns = [
    # ========================================
    # REGULAR USER AUTHENTICATION (Donor & Hospital)
    # ========================================
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('register-page/', views.register_page, name='register_page'),
    path('login-page/', views.login_page, name='login_page'),
    path('logout/', views.logout_view, name='logout'),
    
    # ========================================
    # JWT TOKEN MANAGEMENT
    # ========================================
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # ========================================
    # ADMIN AUTHENTICATION (Requires Secret Key)
    # ========================================
    path('admin/register/', views.admin_register, name='admin_register'),
    path('admin/login/', views.admin_login, name='admin_login'),
    path('admin/register-page/', views.admin_register_page, name='admin_register_page'),
    path('admin/login-page/', views.admin_login_page, name='admin_login_page'),
    
    # ========================================
    # DASHBOARD APIs
    # ========================================
    path('donor/dashboard/', views.donor_dashboard, name='donor_dashboard'),
    path('hospital/dashboard/', views.hospital_dashboard, name='hospital_dashboard'),
]