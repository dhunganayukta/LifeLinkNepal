from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required
def hospital_register(request):
    return render(request, 'hospitals/register.html')


@login_required
def hospital_dashboard(request):
    # dummy list for now
    requests = []

    return render(request, 'hospitals/dashboard.html', {
        'requests': requests
    })


@login_required
def complete_request(request, request_id):
    # later mark request as completed
    return redirect('hospital_dashboard')