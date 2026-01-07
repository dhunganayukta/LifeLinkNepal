from django.urls import path
from . import views
urlpatterns = [
    path('register/', views.register, name='register'),
    path('', views.hospitals_home, name='hospitals_home'),
    
]
