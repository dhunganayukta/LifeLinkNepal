from django.contrib import admin
from django.urls import path, include
from . import views  # Import views from lifelink folder
from donors import views as donor_views
from hospitals import views as hospital_views


urlpatterns = [
    # Main pages
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
       path('contact/create/', views.create_request, name='create_request'),  # ← This is key

    # Admin
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('admin-dashboard/', views.super_admin_dashboard, name='super_admin_dashboard'),
    
    # Apps
    path('accounts/', include('accounts.urls')),
    path('donors/', include('donors.urls')),
    path('hospitals/', include('hospitals.urls')),

    # Direct dashboard links (optional - you might want to remove these)
    path('donor/dashboard/', donor_views.donor_dashboard, name='donor_dashboard'),
    path('hospital/dashboard/', hospital_views.hospital_dashboard, name='hospital_dashboard'),
]