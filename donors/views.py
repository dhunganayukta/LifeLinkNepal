# donors/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from accounts.decorators import role_required
from donors.models import DonorProfile, DonorNotification, DonationHistory, DonorResponse
from donors.forms import DonorProfileUpdateForm
from hospitals.models import BloodRequest, HospitalProfile
from algorithms.blood_compatibility import is_compatible
from algorithms.haversine import haversine_distance
from algorithms.priority import run_priority_algorithm
from algorithms.eligibility import is_donor_eligible
from datetime import date
from collections import defaultdict


# ============================================
# DONOR DASHBOARD
# ============================================
@role_required('donor')
def donor_dashboard(request):
    donor = request.user.donor_profile

    # --------------------------
    # Leaderboard
    # --------------------------
    highest_donor = DonorProfile.objects.order_by('-donation_count').first()
    leaderboard = None
    if highest_donor:
        last_hospital = (
            highest_donor.donation_history.order_by('-date_donated').first().hospital
            if highest_donor.donation_history.exists() else None
        )
        leaderboard = {
            'username': highest_donor.user.username,
            'blood_type': highest_donor.blood_type,
            'hospital_name': last_hospital.hospital_name if last_hospital else None
        }

    # --------------------------
    # Pending blood requests (eligible)
    # --------------------------
    pending_requests = BloodRequest.objects.filter(status='pending')
    eligible_requests = []

    for req in pending_requests:
        if not is_donor_eligible(donor, req):
            continue
        distance = getattr(donor, 'distance', None)
        eligible_requests.append({
            'request': req,
            'hospital_name': req.hospital.hospital_name,
            'hospital_address': req.hospital.address,
            'urgency': req.urgency_level,
            'distance': round(distance, 2) if distance else None,
            'priority_score': calculate_priority_score(req)
        })

    ranked_requests = run_priority_algorithm([r['request'] for r in eligible_requests])
    ranked_requests_data = []
    for item in ranked_requests[:15]:
        req = item['request']
        distance = next((r['distance'] for r in eligible_requests if r['request'] == req), None)
        ranked_requests_data.append({
            'request': req,
            'hospital_name': req.hospital.hospital_name,
            'hospital_address': req.hospital.address,
            'urgency': item['priority_level'],
            'priority_score': item['priority_score'],
            'distance': distance,
        })

    # --------------------------
    # Donation history summary
    # --------------------------
    history = donor.donation_history.all().order_by('-date_donated')
    total_units = sum([d.units_donated for d in history]) if history else 0

    # --------------------------
    # Notifications
    # --------------------------
    # DonorNotification uses 'sent_at' for timestamp (not 'created_at')
    notifications = DonorNotification.objects.filter(donor=donor, is_read=False).order_by('-sent_at')[:10]

    context = {
        'donor': donor,
        'history': history,
        'total_units': total_units,
        'ranked_requests': ranked_requests_data,
        'leaderboard': leaderboard,
        'notifications': notifications,
        'can_donate': donor.can_donate,
        'days_until_eligible': get_days_until_eligible(donor),
    }
    return render(request, 'donors/donor_dashboard.html', context)


# ============================================
# VIEW BLOOD REQUEST DETAIL
# ============================================
@role_required('donor')
def view_blood_request_detail(request, request_id):
    donor = request.user.donor_profile
    blood_request = get_object_or_404(BloodRequest, id=request_id)
    is_eligible = is_donor_eligible(donor, blood_request)
    distance = getattr(donor, 'distance', None)
    priority_score = calculate_priority_score(blood_request)

    context = {
        'blood_request': blood_request,
        'hospital': blood_request.hospital,
        'is_eligible': is_eligible,
        'distance': round(distance, 2) if distance else None,
        'priority_score': priority_score,
        'can_donate': donor.can_donate,
        'donor_blood_type': donor.blood_type,
    }
    return render(request, 'donors/request_detail.html', context)


# ============================================
# ACCEPT BLOOD REQUEST
# ============================================
@role_required('donor')
def accept_blood_request(request, request_id):
    if request.method != 'POST':
        return redirect('donor_dashboard')

    donor = request.user.donor_profile
    blood_request = get_object_or_404(BloodRequest, id=request_id)

    if not is_donor_eligible(donor, blood_request):
        messages.error(request, "You are not eligible to donate for this request yet.")
        return redirect('donor_dashboard')

    DonorResponse.objects.create(
        donor=donor,
        blood_request=blood_request,
        status='accepted',
        response_notes=request.POST.get('notes', '')
    )

    # Update notification
    DonorNotification.objects.filter(donor=donor, blood_request=blood_request).update(
        is_read=True, responded=True
    )

    notify_hospital_of_acceptance(blood_request, donor)
    messages.success(request, f"Thank you! {blood_request.hospital.hospital_name} has been notified.")
    return redirect('donor_dashboard')


# ============================================
# DECLINE BLOOD REQUEST
# ============================================
@role_required('donor')
def decline_blood_request(request, request_id):
    if request.method != 'POST':
        return redirect('donor_dashboard')

    donor = request.user.donor_profile
    blood_request = get_object_or_404(BloodRequest, id=request_id)

    DonorResponse.objects.create(
        donor=donor,
        blood_request=blood_request,
        status='declined',
        response_notes=request.POST.get('reason', '')
    )

    DonorNotification.objects.filter(donor=donor, blood_request=blood_request).update(
        is_read=True, responded=True
    )

    # Notify next eligible donor
    from hospitals.utils import notify_next_eligible_donor
    notify_next_eligible_donor(blood_request)

    messages.info(request, "You declined the request. Next eligible donor will be notified.")
    return redirect('donor_dashboard')


# ============================================
# UPDATE AVAILABILITY
# ============================================
@role_required('donor')
def update_availability(request):
    donor = request.user.donor_profile
    if request.method == 'POST':
        donor.is_available = not donor.is_available
        donor.save()
        status = "available" if donor.is_available else "unavailable"
        messages.success(request, f"Your status has been updated to {status}.")
    return redirect('donor_dashboard')


# ============================================
# EDIT PROFILE
# ============================================
@role_required('donor')
def edit_profile(request):
    donor = request.user.donor_profile
    if request.method == 'POST':
        form = DonorProfileUpdateForm(request.POST, instance=donor)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully!")
            return redirect('donor_dashboard')
        messages.error(request, "Please correct the errors below.")
    else:
        form = DonorProfileUpdateForm(instance=donor)

    return render(request, 'donors/edit_profile.html', {'form': form, 'donor': donor})


# ============================================
# DONATION HISTORY
# ============================================
@role_required('donor')
def donation_history(request):
    donor = request.user.donor_profile
    history = DonationHistory.objects.filter(donor=donor).order_by('-date_donated')
    total_donations = history.count()
    total_units = sum(d.units_donated for d in history) if history else 0

    # Timeline by year
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


# ============================================
# FIND NEARBY HOSPITALS
# ============================================
@role_required('donor')
def find_nearby_hospitals(request):
    donor = request.user.donor_profile
    if not (donor.latitude and donor.longitude):
        messages.error(request, "Please update your location first.")
        return redirect('donor_dashboard')

    all_hospitals = HospitalProfile.objects.filter(is_verified=True)
    nearby_hospitals = []

    for hospital in all_hospitals:
        if hospital.latitude and hospital.longitude:
            distance = haversine_distance(
                donor.latitude, donor.longitude,
                hospital.latitude, hospital.longitude
            )
            if distance <= 50:
                active_requests = BloodRequest.objects.filter(hospital=hospital, status='pending')
                compatible = [r for r in active_requests if is_compatible(donor.blood_type, r.blood_type)]
                nearby_hospitals.append({
                    'hospital': hospital,
                    'distance': round(distance, 2),
                    'total_requests': active_requests.count(),
                    'compatible_requests': len(compatible),
                })

    nearby_hospitals.sort(key=lambda x: x['distance'])
    return render(request, 'donors/nearby_hospitals.html', {
        'donor': donor,
        'nearby_hospitals': nearby_hospitals[:20]
    })


# ============================================
# MARK NOTIFICATIONS
# ============================================
@role_required('donor')
def mark_notification_read(request, notification_id):
    try:
        notification = DonorNotification.objects.get(id=notification_id, donor=request.user.donor_profile)
        notification.is_read = True
        notification.save()
        messages.success(request, "Notification marked as read.")
    except DonorNotification.DoesNotExist:
        messages.error(request, "Notification not found.")
    return redirect('donor_dashboard')


@role_required('donor')
def mark_all_notifications_read(request):
    DonorNotification.objects.filter(donor=request.user.donor_profile, is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect('donor_dashboard')


# ============================================
# NOTIFICATION UTILITY
# ============================================
def notify_hospital_of_acceptance(blood_request, donor):
    hospital = blood_request.hospital
    message = f"""
    GOOD NEWS! A donor has accepted your blood request.
    
    Request ID: {blood_request.id}
    Blood Type Needed: {blood_request.blood_type}
    
    DONOR DETAILS:
    Username: {donor.user.username}
    Blood Type: {donor.blood_type}
    Request Urgency: {blood_request.urgency_level}
    
    The donor will coordinate with you through the platform.
    """
    print(f"Notification to {hospital.hospital_name}: {message}")


# ============================================
# HELPER FUNCTIONS
# ============================================
def get_days_until_eligible(donor):
    if not donor.last_donation_date:
        return 0
    days_since = (date.today() - donor.last_donation_date).days
    return max(0, 90 - days_since)


def calculate_priority_score(blood_request):
    """Placeholder priority scoring. Replace with your algorithm."""
    urgency_scores = {'critical': 3, 'high': 2, 'medium': 1, 'low': 0}
    return urgency_scores.get(blood_request.urgency_level, 0)
