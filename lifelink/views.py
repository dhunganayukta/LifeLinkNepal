# lifelink/views.py - Your main project views.py (UPDATED)

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .models import ContactRequest

# ========================================
# PUBLIC PAGES
# ========================================

def home(request):
    """Home page with blood types"""
    blood_types = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    return render(request, "home.html", {
        "blood_types": blood_types
    })


def about(request):
    """About page"""
    return render(request, 'about.html')


def contact(request):
    """Contact page"""
    return render(request, 'contact.html')


def create_request(request):
    """Handle contact form submission"""
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        subject = request.POST.get('subject')
        message = request.POST.get('message')

        ContactRequest.objects.create(
            name=name,
            email=email,
            phone=phone,
            subject=subject,
            message=message
        )

        messages.success(request, "Your message has been sent successfully!")
        return redirect('contact')

    return render(request, 'contact.html')


# ========================================
# DASHBOARD ROUTING SYSTEM (NEW!)
# ========================================

@login_required
def dashboard_router(request):
    """
    Smart router that automatically redirects users to their appropriate dashboard
    This is a BACKUP route - usually the frontend handles routing via JavaScript
    """
    user = request.user
    
    # Check if user is super admin (staff/superuser)
    if user.is_staff or user.is_superuser:
        return redirect('super_admin_dashboard')
    
    # Check if user has donor profile
    elif hasattr(user, 'donor_profile'):
        return redirect('donor_dashboard')
    
    # Check if user has hospital profile  
    elif hasattr(user, 'hospital_profile'):
        return redirect('hospital_dashboard')
    
    # Fallback - something went wrong
    else:
        messages.error(request, "Unable to determine user type. Please contact support.")
        return redirect('home')


@login_required
def super_admin_dashboard(request):
    """
    Super Admin Dashboard - Only accessible to staff/superuser
    Shows ALL donors, hospitals, and blood requests
    """
    # Security check: Only staff/superuser can access
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "⛔ Access denied. Admin privileges required.")
        return redirect('dashboard_router')
    
    context = {
        'user_type': 'super_admin',
        'user': request.user,
        'admin_name': request.user.username,
    }
    return render(request, 'super_admin_dashboard.html', context)


# ========================================
# UTILITY FUNCTIONS
# ========================================

def check_user_type(user):
    """
    Helper function to determine user type
    Returns: 'super_admin', 'donor', 'hospital', or None
    """
    if user.is_staff or user.is_superuser:
        return 'super_admin'
    elif hasattr(user, 'donor_profile'):
        return 'donor'
    elif hasattr(user, 'hospital_profile'):
        return 'hospital'
    else:
        return None