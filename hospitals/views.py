from django.shortcuts import render

# Create your views here.
def register(request):
    return render(request, 'hospitals/register.html')
def hospitals_home(request):
    return render(request, 'hospitals/home.html')
