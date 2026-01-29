# donors/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from accounts.decorators import role_required
from donors.models import DonorProfile, Notification
from hospitals.models import BloodRequest
from algorithms.blood_compatibility import get_compatible_donors, is_compatible
from algorithms.haversine import haversine_distance
from algorithms.priority import run_priority_algorithm


@role_required('donor')
def donor_dashboard(request):
    """
    Enhanced Donor Dashboard with Algorithm Integration
    
    Algorithms Used:
    1. Blood Compatibility - Show only requests donor can fulfill
    2. Haversine Distance - Show only nearby hospitals (within 50km)
    3. Priority Algorithm - Rank requests by urgency
    """
    try:
        donor = DonorProfile.objects.get(user=request.user)
    except DonorProfile.DoesNotExist:
        messages.error(request, "Donor profile not found.")
        return redirect('register')
    
    # ============================================
    # ALGORITHM 1: BLOOD COMPATIBILITY FILTERING
    # ============================================
    # Get all pending blood requests
    all_pending_requests = BloodRequest.objects.filter(status='pending')
    
    # Filter by blood compatibility
    compatible_requests = []
    for blood_request in all_pending_requests:
        # Check if donor's blood type can donate to this request
        if is_compatible(donor.blood_type, blood_request.blood_type):
            compatible_requests.append(blood_request)
    
    # ============================================
    # ALGORITHM 2: HAVERSINE DISTANCE FILTERING
    # ============================================
    # Only show requests from hospitals within 50km
    nearby_requests = []
    request_distances = {}
    
    if donor.latitude and donor.longitude:
        for blood_request in compatible_requests:
            hospital = blood_request.hospital
            
            if hospital.latitude and hospital.longitude:
                # Calculate distance
                distance = haversine_distance(
                    donor.latitude,
                    donor.longitude,
                    hospital.latitude,
                    hospital.longitude
                )
                
                # Only include if within 50km
                if distance <= 50:
                    nearby_requests.append(blood_request)
                    request_distances[blood_request.id] = distance
    else:
        # If donor location not set, show all compatible requests
        nearby_requests = compatible_requests
        messages.warning(request, "Please update your location for better matches.")
    
    # ============================================
    # ALGORITHM 3: PRIORITY RANKING
    # ============================================
    # Rank the nearby compatible requests by priority
    ranked_requests = run_priority_algorithm(nearby_requests)
    
    # Prepare data for template with all relevant info
    request_data = []
    for item in ranked_requests[:15]:  # Show top 15 most urgent
        req = item['request']
        
        request_data.append({
            'request': req,
            'hospital_name': req.hospital.hospital_name,
            'hospital_address': req.hospital.address,
            'hospital_phone': req.hospital.phone,
            'distance': round(request_distances.get(req.id, 0), 1),
            'priority_score': item['priority_score'],
            'priority_level': item['priority_level'],
            'priority_badge': get_priority_badge_class(item['priority_level']),
            'urgency_icon': get_urgency_icon(req.urgency_level),
            'blood_type_match': get_blood_type_compatibility_text(donor.blood_type, req.blood_type),
            'hours_waiting': round(req.hours_waiting, 1),
        })
    
    # Get donor's donation history
    history = donor.donation_history.all().order_by('-date_donated') if hasattr(donor, 'donation_history') else []
    
    # Get unread notifications
    notifications = Notification.objects.filter(
        donor=donor, 
        is_read=False
    ).order_by('-created_at')[:10]
    
    # Calculate donor statistics
    stats = {
        'total_donations': donor.donation_count or 0,
        'can_donate_now': donor.can_donate,
        'days_until_eligible': get_days_until_eligible(donor),
        'compatible_requests_count': len(compatible_requests),
        'nearby_requests_count': len(nearby_requests),
        'critical_requests_count': len([r for r in ranked_requests if r['priority_level'] == 'critical']),
    }
    
    context = {
        'donor': donor,
        'request_data': request_data,
        'history': history,
        'notifications': notifications,
        'stats': stats,
        'show_location_warning': not (donor.latitude and donor.longitude),
    }
    
    return render(request, 'donors/donor_dashboard.html', context)


@role_required('donor')
def view_blood_request_detail(request, request_id):
    """
    Detailed view of a specific blood request with route calculation
    """
    donor = request.user.donorprofile
    blood_request = get_object_or_404(BloodRequest, id=request_id)
    
    # Check compatibility
    is_blood_compatible = is_compatible(donor.blood_type, blood_request.blood_type)
    
    # Calculate distance
    distance = None
    if donor.latitude and blood_request.hospital.latitude:
        distance = haversine_distance(
            donor.latitude,
            donor.longitude,
            blood_request.hospital.latitude,
            blood_request.hospital.longitude
        )
    
    # Calculate priority
    from algorithms.priority import calculate_priority_score
    priority_score = calculate_priority_score(blood_request)
    
    context = {
        'blood_request': blood_request,
        'hospital': blood_request.hospital,
        'is_compatible': is_blood_compatible,
        'distance': round(distance, 2) if distance else None,
        'priority_score': priority_score,
        'can_donate': donor.can_donate,
        'donor_blood_type': donor.blood_type,
    }
    
    return render(request, 'donors/request_detail.html', context)


@role_required('donor')
def accept_blood_request(request, request_id):
    """
    Donor accepts a blood request
    """
    if request.method != 'POST':
        return redirect('donor_dashboard')
    
    donor = request.user.donorprofile
    blood_request = get_object_or_404(BloodRequest, id=request_id)
    
    # Validate donor can donate
    if not donor.can_donate:
        messages.error(request, "You are not eligible to donate yet. Please wait 90 days since your last donation.")
        return redirect('donor_dashboard')
    
    # Check blood compatibility
    if not is_compatible(donor.blood_type, blood_request.blood_type):
        messages.error(request, "Your blood type is not compatible with this request.")
        return redirect('donor_dashboard')
    
    # Create response record
    from hospitals.models import DonorResponse
    response = DonorResponse.objects.create(
        donor=donor,
        blood_request=blood_request,
        status='accepted',
        response_notes=request.POST.get('notes', '')
    )
    
    # Mark notification as read/responded
    Notification.objects.filter(
        donor=donor,
        blood_request=blood_request
    ).update(is_read=True, responded=True)
    
    # Send notification to hospital
    send_hospital_notification(blood_request.hospital, donor, blood_request)
    
    messages.success(
        request, 
        f"Thank you! {blood_request.hospital.hospital_name} has been notified. They will contact you at {donor.phone}."
    )
    
    return redirect('donor_dashboard')


@role_required('donor')
def decline_blood_request(request, request_id):
    """
    Donor declines a blood request
    """
    if request.method != 'POST':
        return redirect('donor_dashboard')
    
    donor = request.user.donorprofile
    blood_request = get_object_or_404(BloodRequest, id=request_id)
    
    # Create response record
    from hospitals.models import DonorResponse
    DonorResponse.objects.create(
        donor=donor,
        blood_request=blood_request,
        status='declined',
        response_notes=request.POST.get('reason', '')
    )
    
    # Mark notification as read/responded
    Notification.objects.filter(
        donor=donor,
        blood_request=blood_request
    ).update(is_read=True, responded=True)
    
    messages.info(request, "Response recorded. Thank you for your time.")
    
    return redirect('donor_dashboard')


@role_required('donor')
def update_availability(request):
    """
    Toggle donor availability status
    """
    donor = request.user.donorprofile
    
    if request.method == 'POST':
        donor.is_available = not donor.is_available
        donor.save()
        
        status = "available" if donor.is_available else "unavailable"
        messages.success(request, f"Your status has been updated to {status}.")
    
    return redirect('donor_dashboard')


@role_required('donor')
def find_nearby_hospitals(request):
    """
    Show all hospitals within donor's area with their current blood needs
    Uses Haversine algorithm to find nearby hospitals
    """
    donor = request.user.donorprofile
    
    if not (donor.latitude and donor.longitude):
        messages.error(request, "Please update your location first.")
        return redirect('donor_dashboard')
    
    # Get all hospitals
    from hospitals.models import HospitalProfile
    all_hospitals = HospitalProfile.objects.filter(is_verified=True)
    
    # Calculate distances
    nearby_hospitals = []
    for hospital in all_hospitals:
        if hospital.latitude and hospital.longitude:
            distance = haversine_distance(
                donor.latitude,
                donor.longitude,
                hospital.latitude,
                hospital.longitude
            )
            
            if distance <= 50:  # Within 50km
                # Get active blood requests from this hospital
                active_requests = BloodRequest.objects.filter(
                    hospital=hospital,
                    status='pending'
                )
                
                # Filter compatible requests
                compatible = [
                    req for req in active_requests 
                    if is_compatible(donor.blood_type, req.blood_type)
                ]
                
                nearby_hospitals.append({
                    'hospital': hospital,
                    'distance': round(distance, 2),
                    'total_requests': active_requests.count(),
                    'compatible_requests': len(compatible),
                })
    
    # Sort by distance
    nearby_hospitals.sort(key=lambda x: x['distance'])
    
    context = {
        'donor': donor,
        'nearby_hospitals': nearby_hospitals[:20],  # Show top 20
    }
    
    return render(request, 'donors/nearby_hospitals.html', context)


# ============================================
# UTILITY FUNCTIONS
# ============================================

def get_priority_badge_class(priority_level):
    """Get Bootstrap badge class for priority level"""
    badges = {
        'critical': 'danger',
        'high': 'warning',
        'medium': 'info',
        'low': 'secondary',
    }
    return badges.get(priority_level, 'secondary')


def get_urgency_icon(urgency_level):
    """Get icon for urgency level"""
    icons = {
        'critical': 'bi-exclamation-triangle-fill text-danger',
        'urgent': 'bi-exclamation-circle-fill text-warning',
        'normal': 'bi-info-circle-fill text-info',
    }
    return icons.get(urgency_level, 'bi-info-circle')


def get_blood_type_compatibility_text(donor_type, needed_type):
    """Get compatibility description"""
    if donor_type == needed_type:
        return "Exact Match"
    else:
        return "Compatible"


def get_days_until_eligible(donor):
    """Calculate days until donor can donate again"""
    if not donor.last_donation_date:
        return 0
    
    from datetime import date
    days_since = (date.today() - donor.last_donation_date).days
    
    if days_since >= 90:
        return 0
    
    return 90 - days_since


def send_hospital_notification(hospital, donor, blood_request):
    """
    Notify hospital that a donor has accepted
    """
    message = f"""
    GOOD NEWS! A donor has accepted your blood request.
    
    Request ID: {blood_request.id}
    Blood Type Needed: {blood_request.blood_type}
    
    DONOR DETAILS:
    Name: {donor.full_name}
    Blood Type: {donor.blood_type}
    Phone: {donor.phone}
    Location: {donor.address}
    
    Please contact them immediately.
    """
    
    # TODO: Implement SMS/Email notification
    print(f"Notification to {hospital.hospital_name}: {message}")

@role_required('donor')
def edit_profile(request):
    """
    Edit donor profile with location update
    """
    from .forms import DonorProfileUpdateForm
    from .models import DonorProfile
    
    try:
        donor = request.user.donorprofile
    except DonorProfile.DoesNotExist:
        messages.error(request, "Donor profile not found.")
        return redirect('register')
    
    if request.method == 'POST':
        form = DonorProfileUpdateForm(request.POST, instance=donor)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully!")
            return redirect('donor_dashboard')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = DonorProfileUpdateForm(instance=donor)
    
    context = {
        'form': form,
        'donor': donor,
    }
    
    return render(request, 'donors/edit_profile.html', context)


@role_required('donor')
def donation_history(request):
    """
    Full donation history page with statistics
    """
    from .models import DonorProfile, DonationHistory
    
    try:
        donor = request.user.donorprofile
    except DonorProfile.DoesNotExist:
        messages.error(request, "Donor profile not found.")
        return redirect('register')
    
    # Get all donation history
    history = DonationHistory.objects.filter(donor=donor).order_by('-date_donated')
    
    # Calculate statistics
    total_donations = history.count()
    total_units = sum([d.units_donated for d in history]) if history else 0
    
    # Group by year for timeline display
    from collections import defaultdict
    history_by_year = defaultdict(list)
    for donation in history:
        history_by_year[donation.date_donated.year].append(donation)
    
    context = {
        'donor': donor,
        'history': history,
        'total_donations': total_donations,
        'total_units': total_units,
        'history_by_year': dict(sorted(history_by_year.items(), reverse=True)),
    }
    
    return render(request, 'donors/donation_history.html', context)
@role_required('donor')
def mark_notification_read(request, notification_id):
    """
    Mark a single notification as read
    """
    try:
        notification = Notification.objects.get(
            id=notification_id,
            donor=request.user.donorprofile
        )
        notification.is_read = True
        notification.save()
        messages.success(request, "Notification marked as read.")
    except Notification.DoesNotExist:
        messages.error(request, "Notification not found.")
    
    return redirect('donor_dashboard')

@role_required('donor')
def mark_all_notifications_read(request):
    """
    Mark all notifications as read
    """
    try:
        Notification.objects.filter(
            donor=request.user.donorprofile,
            is_read=False
        ).update(is_read=True)
        messages.success(request, "All notifications marked as read.")
    except Exception as e:
        messages.error(request, "Could not mark notifications as read.")
    
    return redirect('donor_dashboard')


# ============================================
# ALGORITHM USAGE SUMMARY FOR DONORS
# ============================================
"""
DONOR VIEW ALGORITHMS:

1. BLOOD COMPATIBILITY (blood_compatibility.py)
   ✅ Filter blood requests donor can fulfill
   ✅ Show only compatible requests
   ✅ Validate before accepting request

2. HAVERSINE DISTANCE (haversine.py)
   ✅ Show only nearby hospitals (within 50km)
   ✅ Calculate distance to each hospital
   ✅ Sort hospitals by proximity
   ✅ Find nearby hospitals feature

3. PRIORITY ALGORITHM (priority.py)
   ✅ Rank blood requests by urgency
   ✅ Show most critical requests first
   ✅ Help donors prioritize who to help

DONOR WORKFLOW:
1. Donor logs in → See compatible requests (Blood Compatibility)
2. Filter by distance (Haversine) → Only show nearby hospitals
3. Rank by priority (Priority Algorithm) → Most urgent first
4. Donor accepts → Hospital gets notification with donor contact
5. Donation completed → Update donor history

WHY DONORS NEED ALGORITHMS:
- Without algorithms: Donor sees ALL requests (overwhelming, irrelevant)
- With algorithms: Donor sees only relevant, nearby, urgent requests
- Result: Better user experience, faster response times, more donations
"""