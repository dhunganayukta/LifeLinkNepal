# lifelink/views.py

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .models import ContactRequest


# ========================================
# PUBLIC PAGES
# ========================================

def home(request):
    """Home page with blood types"""
    blood_types = [
        ("A+",  "Type A Positive",  "Donates to A+ and AB+",         None),
        ("A−",  "Type A Negative",  "Donates to A+, A−, AB+, AB−",  None),
        ("B+",  "Type B Positive",  "Donates to B+ and AB+",         None),
        ("B−",  "Type B Negative",  "Donates to B+, B−, AB+, AB−",  None),
        ("O+",  "Type O Positive",  "Most common blood type",         None),
        ("O−",  "Type O Negative",  "Donates to all blood types",     "Universal Donor"),
        ("AB+", "Type AB Positive", "Receives from all types",        "Universal Recipient"),
        ("AB−", "Type AB Negative", "Rare — only 1% of people",       None),
    ]
    return render(request, 'home.html', {'blood_types': blood_types})


def about(request):
    """About page"""
    return render(request, 'about.html')


def contact(request):
    """Contact page"""
    return render(request, 'contact.html')


def create_request(request):
    """Handle contact form submission"""
    if request.method == 'POST':
        name    = request.POST.get('name')
        email   = request.POST.get('email')
        phone   = request.POST.get('phone')
        subject = request.POST.get('subject')
        message = request.POST.get('message')

        ContactRequest.objects.create(
            name=name,
            email=email,
            phone=phone,
            subject=subject,
            message=message,
        )

        messages.success(request, "Your message has been sent successfully!")
        return redirect('contact')

    return render(request, 'contact.html')


# ========================================
# SUPER ADMIN DASHBOARD
# ========================================

@login_required
def super_admin_dashboard(request):
    """
    Super Admin Dashboard — only accessible to staff/superuser.
    Shows all donors, hospitals, and blood requests.
    """
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "⛔ Access denied. Admin privileges required.")
        return redirect('home')

    context = {
        'user_type': 'super_admin',
        'user':       request.user,
        'admin_name': request.user.username,
    }
    return render(request, 'super_admin_dashboard.html', context)


# ========================================
# UTILITY FUNCTIONS
# ========================================

def check_user_type(user):
    """
    Helper to determine user type.
    Returns: 'super_admin', 'donor', 'hospital', or None.
    """
    if user.is_staff or user.is_superuser:
        return 'super_admin'
    elif hasattr(user, 'donor_profile'):
        return 'donor'
    elif hasattr(user, 'hospital_profile'):
        return 'hospital'
    return None