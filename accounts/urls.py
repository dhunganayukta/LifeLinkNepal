from django.urls import path
from . import views

urlpatterns = [

    path('', views.accounts_home, name='accounts_home'), 
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
]
    