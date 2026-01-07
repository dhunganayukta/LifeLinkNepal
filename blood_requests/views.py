from django.shortcuts import render

# Create your views here.

def blood_requests_home(request):
    return render(request, 'blood_requests/home.html')

def emergency(request):
    return render(request, 'blood_requests/emergency.html')