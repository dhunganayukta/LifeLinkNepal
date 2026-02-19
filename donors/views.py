# donors/views.py (FIXED VERSION - Simplified Permission Checks)
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
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
from django.core.mail import send_mail
from django.conf import settings


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
    # ACTIVE Notifications (waiting for response)
    # --------------------------
    active_notifications = DonorNotification.objects.filter(
        donor=donor,
        status='notified',  # Only notified ones need response
        is_notified=True
    ).select_related('blood_request', 'blood_request__hospital').order_by('-notified_at')

    # --------------------------
    # Past Notifications
    # --------------------------
    past_notifications = DonorNotification.objects.filter(
        donor=donor
    ).exclude(status='notified').select_related(
        'blood_request', 'blood_request__hospital'
    ).order_by('-sent_at')[:10]

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

    context = {
        'donor': donor,
        'history': history,
        'total_units': total_units,
        'ranked_requests': ranked_requests_data,
        'leaderboard': leaderboard,
        'active_notifications': active_notifications,
        'past_notifications': past_notifications,
        'can_donate': donor.can_donate,
        'days_until_eligible': get_days_until_eligible(donor),
        'lives_saved': len(history) * 3,
    }
    return render(request, 'donors/donor_dashboard.html', context)


# ============================================
# VIEW NOTIFICATION DETAIL
# ============================================
@role_required('donor')
def view_notification_detail(request, notification_id):
    """View full details of a blood request notification"""
    notification = get_object_or_404(
        DonorNotification,
        id=notification_id,
        donor=request.user.donor_profile
    )
    
    # Mark as read
    notification.is_read = True
    notification.save()
    
    blood_request = notification.blood_request
    hospital = blood_request.hospital
    
    context = {
        'notification': notification,
        'blood_request': blood_request,
        'hospital': hospital,
        'can_respond': notification.status == 'notified',
    }
    return render(request, 'donors/notification_detail.html', context)


# ============================================
# ACCEPT BLOOD REQUEST (FIXED - SIMPLIFIED)
# ============================================
@role_required('donor')
def accept_blood_request(request, notification_id):
    """
    Donor accepts blood request via notification
    - Updates notification status to 'accepted'
    - Cancels all other pending notifications for this request
    - Notifies hospital (limited info: username, blood type, distance)
    - Notifies admin
    """
    # Get notification - automatically checks it belongs to logged-in donor
    notification = get_object_or_404(
        DonorNotification,
        id=notification_id,
        donor=request.user.donor_profile
    )
    
    # Check if notification is still active
    if notification.status != 'notified':
        if notification.status == 'accepted':
            messages.warning(request, "You have already accepted this request.")
        elif notification.status == 'rejected':
            messages.warning(request, "You have already rejected this request.")
        elif notification.status == 'cancelled':
            messages.info(request, "This request has been cancelled or fulfilled by another donor.")
        else:
            messages.error(request, "This notification is no longer active.")
        return redirect('donor_dashboard')
    
    if request.method == 'POST':
        donor = notification.donor
        blood_request = notification.blood_request
        
        # Update notification status
        notification.status = 'accepted'
        notification.responded_at = timezone.now()
        notification.response_notes = request.POST.get('notes', '')
        notification.responded = True
        notification.save()
        
        # Also create DonorResponse for backward compatibility
        DonorResponse.objects.create(
            donor=donor,
            blood_request=blood_request,
            status='accepted',
            response_notes=notification.response_notes
        )
        
        # Cancel all other pending/notified notifications for this request
        DonorNotification.objects.filter(
            blood_request=blood_request,
            status__in=['pending', 'notified']
        ).exclude(id=notification_id).update(status='cancelled')
        
        # Notify hospital (LIMITED INFO: username, blood type, distance only)
        send_hospital_acceptance_notification(donor, blood_request, notification.distance)
        
        # Notify admin
        send_admin_acceptance_notification(blood_request, donor, notification)
        
        messages.success(
            request,
            f"✅ You have accepted the blood request from {blood_request.hospital.hospital_name}. "
            f"The hospital has been notified and will contact you shortly."
        )
        
        return redirect('donor_dashboard')
    
    context = {
        'notification': notification,
        'blood_request': notification.blood_request,
    }
    return render(request, 'donors/confirm_accept.html', context)


# ============================================
# REJECT BLOOD REQUEST (FIXED - SIMPLIFIED)
# ============================================
@role_required('donor')
def reject_blood_request(request, notification_id):
    """
    Donor rejects blood request
    - Updates notification status to 'rejected'
    - Notifies admin to trigger next donor notification
    """
    # Get notification - automatically checks it belongs to logged-in donor
    notification = get_object_or_404(
        DonorNotification,
        id=notification_id,
        donor=request.user.donor_profile
    )
    
    # Check if notification is still active
    if notification.status != 'notified':
        if notification.status == 'accepted':
            messages.warning(request, "You have already accepted this request.")
        elif notification.status == 'rejected':
            messages.warning(request, "You have already rejected this request.")
        elif notification.status == 'cancelled':
            messages.info(request, "This request has been cancelled or fulfilled by another donor.")
        else:
            messages.error(request, "This notification is no longer active.")
        return redirect('donor_dashboard')
    
    if request.method == 'POST':
        rejection_reason = request.POST.get('reason', 'Not specified')
        donor = notification.donor
        blood_request = notification.blood_request
        
        # Update notification status
        notification.status = 'rejected'
        notification.responded_at = timezone.now()
        notification.response_notes = rejection_reason
        notification.responded = True
        notification.save()
        
        # Also create DonorResponse for backward compatibility
        DonorResponse.objects.create(
            donor=donor,
            blood_request=blood_request,
            status='declined',
            response_notes=rejection_reason
        )
        
        # Notify admin about rejection (admin will manually notify next donor)
        send_admin_rejection_notification(blood_request, donor, rejection_reason)
        
        messages.info(
            request,
            f"You have declined the blood request. "
            f"Admin has been notified and will contact the next available donor."
        )
        
        return redirect('donor_dashboard')
    
    # If GET request, show confirmation page (optional - can skip if using inline forms)
    context = {
        'notification': notification,
        'blood_request': notification.blood_request,
    }
    return render(request, 'donors/confirm_reject.html', context)


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
# VIEW DONOR DETAIL (for hospitals)
# ============================================
@role_required('hospital')
def view_donor_detail(request, donor_id):
    """
    Limited donor detail for hospital users. Shows username, blood type and distance only.
    """
    donor = get_object_or_404(DonorProfile, id=donor_id)
    # Try to get hospital profile from request user
    hospital_profile = getattr(request.user, 'hospitalprofile', None)

    distance = None
    if hospital_profile and donor.latitude and donor.longitude and hospital_profile.latitude and hospital_profile.longitude:
        distance = haversine_distance(hospital_profile.latitude, hospital_profile.longitude, donor.latitude, donor.longitude)

    context = {
        'donor': donor,
        'distance': round(distance, 2) if distance is not None else None,
        'hospital': hospital_profile,
    }
    return render(request, 'donors/view_donor_detail.html', context)


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
# NOTIFICATION UTILITY FUNCTIONS
# ============================================
def send_hospital_acceptance_notification(donor, blood_request, distance):
    """
    Notify hospital when donor accepts
    Hospital only sees: username, blood type, distance (PRIVACY PROTECTED)
    """
    hospital = blood_request.hospital
    
    message = f"""
✅ DONOR ACCEPTED YOUR BLOOD REQUEST!

Request for: {blood_request.patient_name}
Blood Type Required: {blood_request.blood_type}

DONOR DETAILS (Limited Info):
Username: {donor.user.username}
Blood Type: {donor.blood_type}
Distance: {distance:.2f}km

The donor has been notified and will coordinate with you through the platform messaging system.

Thank you for using LifeLink Nepal!
    """.strip()
    
    # Send email to hospital
    if hospital.user.email:
        try:
            send_mail(
                subject=f"✅ Donor Accepted - Blood Request #{blood_request.id}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[hospital.user.email],
                fail_silently=False,
            )
            print(f"📧 Email sent to hospital: {hospital.hospital_name}")
        except Exception as e:
            print(f"❌ Failed to send email to hospital: {e}")
    
    print(f"✅ Hospital notified: Donor {donor.user.username} accepted request #{blood_request.id}")


def send_admin_acceptance_notification(blood_request, donor, notification):
    """Notify admin that donor accepted"""
    from django.contrib.auth import get_user_model
    User = get_user_model()

    admins = User.objects.filter(is_superuser=True, is_active=True)
    
    message = f"""
✅ DONOR ACCEPTED BLOOD REQUEST

Request ID: #{blood_request.id}
Hospital: {blood_request.hospital.hospital_name}
Patient: {blood_request.patient_name}
Blood Type: {blood_request.blood_type}

ACCEPTED BY:
Donor: {donor.full_name}
Username: {donor.user.username}
Phone: {donor.phone}
Blood Type: {donor.blood_type}
Distance: {notification.distance:.2f}km

Response Time: {notification.response_time_hours} hours

View in admin: {settings.SITE_URL}/admin/hospitals/bloodrequest/{blood_request.id}/change/
    """.strip()
    
    admin_emails = [admin.email for admin in admins if admin.email]
    if admin_emails:
        try:
            send_mail(
                subject=f"✅ Donor Accepted - Request #{blood_request.id}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=False,
            )
            print(f"📧 Email sent to {len(admin_emails)} admin(s)")
        except Exception as e:
            print(f"❌ Failed to send email to admins: {e}")
    
    print(f"✅ Admin notified: Donor {donor.full_name} accepted")


def send_admin_rejection_notification(blood_request, donor, reason):
    """Notify admin that donor rejected - admin needs to notify next donor"""
    from django.contrib.auth import get_user_model
    User = get_user_model()

    admins = User.objects.filter(is_superuser=True, is_active=True)
    
    # Get next donor in queue
    next_notification = DonorNotification.objects.filter(
        blood_request=blood_request,
        is_notified=False,
        status='pending'
    ).order_by('priority_order').first()
    
    next_donor_info = ""
    if next_notification:
        next_donor_info = f"\nNEXT DONOR: {next_notification.donor.full_name} (Priority #{next_notification.priority_order})"
    else:
        next_donor_info = "\n⚠️ NO MORE DONORS AVAILABLE IN QUEUE"
    
    message = f"""
❌ DONOR REJECTED BLOOD REQUEST

Request ID: #{blood_request.id}
Hospital: {blood_request.hospital.hospital_name}
Patient: {blood_request.patient_name}
Blood Type: {blood_request.blood_type}

REJECTED BY:
Donor: {donor.full_name}
Reason: {reason}
{next_donor_info}

ACTION REQUIRED:
Please login to admin panel and click "Notify Next Donor"
Link: {settings.SITE_URL}/admin/hospitals/bloodrequest/{blood_request.id}/change/
    """.strip()
    
    admin_emails = [admin.email for admin in admins if admin.email]
    if admin_emails:
        try:
            send_mail(
                subject=f"❌ Donor Rejected - Action Required - Request #{blood_request.id}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=False,
            )
            print(f"📧 Email sent to {len(admin_emails)} admin(s)")
        except Exception as e:
            print(f"❌ Failed to send email to admins: {e}")
    
    print(f"❌ Admin notified: Donor {donor.full_name} rejected")


def notify_hospital_of_acceptance(blood_request, donor):
    """OLD FUNCTION - kept for backward compatibility"""
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