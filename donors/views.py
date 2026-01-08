from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required
def donor_register(request):
    return render(request, 'donors/register.html')


@login_required
def donor_dashboard(request):
    # dummy data (replace with DB later)
    requests_nearby = []

    return render(request, 'donors/dashboard.html', {
        'requests_nearby': requests_nearby
    })


@login_required
def accept_request(request, request_id):
    # later update request status in DB
    return redirect('donor_dashboard')