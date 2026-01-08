from django.urls import path
from . import views
urlpatterns = [
  path('register/',views.donor_register,name='donor_register'),
    path('dashboard/',views.donor_dashboard,name='donor_dashboard'),
    path('accept/<int:request_id>/',views.accept_request,name='accept_request'),

]