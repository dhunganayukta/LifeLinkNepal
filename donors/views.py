from django.shortcuts import render

# Create your views here.
def register(request):
    return render(request, 'donors/register.html')
def donors_home(request):
    return render(request, 'donors/home.html')
