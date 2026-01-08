from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            if user.user_type == 'donor':
                return redirect('donor-dashboard')
            elif user.user_type == 'hospital':
                return redirect('hospital-dashboard')
        else:
            return render(request, 'accounts/login.html', {'error': 'Invalid credentials'})

    return render(request, 'accounts/login.html')


def register_view(request):
    return render(request, 'accounts/register.html')


def logout_view(request):
    logout(request)
    return redirect('home')