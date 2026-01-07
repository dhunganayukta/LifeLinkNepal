from django.shortcuts import render


def accounts_home(request):
    return render(request, 'accounts/home.html')


def register(request):
    return render(request, "accounts/register.html")

def login_view(request):
    return render(request, "accounts/login.html")
