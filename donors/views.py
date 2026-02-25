from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
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

POINTS_PER_DONATION = 50


# ============================================
# DONOR DASHBOARD
# ============================================
@role_required('donor')
def donor_dashboard(request):
    donor = request.user.donor_profile

    # Leaderboard
    highest_donor = DonorProfile.objects.order_by('-donation_count').first()
    leaderboard = None
    if highest_donor:
        last_donation = highest_donor.donation_history.order_by('-date_donated').first()
        last_hospital = last_donation.hospital if last_donation else None
        leaderboard = {
            'username':    highest_donor.user.username,
            'blood_type':  highest_donor.blood_type,
            'hospital_name': last_hospital.hospital_name if last_hospital else None,
            'points':      highest_donor.points,
        }

    # Active notifications (waiting for donor response)
    active_notifications = DonorNotification.objects.filter(
        donor=donor,
        status='notified',
        is_notified=True
    ).select_related('blood_request', 'blood_request__hospital').order_by('-notified_at')

    # Past notifications (for accordion — rendered by JS via /dashboard/data/)
    past_notifications = DonorNotification.objects.filter(
        donor=donor
    ).exclude(status='notified').select_related(
        'blood_request', 'blood_request__hospital'
    ).order_by('-sent_at')[:10]

    # Eligible pending blood requests within distance
    pending_requests = BloodRequest.objects.filter(status='pending')
    eligible_requests = []

    try:
        max_distance = float(request.GET.get('distance', 25))
    except (ValueError, TypeError):
        max_distance = 25

    for req in pending_requests:
        if not is_donor_eligible(donor, req):
            continue

        distance = None
        if (donor.latitude and donor.longitude and
                req.hospital.latitude and req.hospital.longitude):
            distance = haversine_distance(
                donor.latitude, donor.longitude,
                req.hospital.latitude, req.hospital.longitude
            )

        if distance is None or distance > max_distance:
            continue

        eligible_requests.append({
            'request':        req,
            'hospital_name':  req.hospital.hospital_name,
            'hospital_address': req.hospital.address,
            'urgency':        req.urgency_level,
            'distance':       round(distance, 2),
            'priority_score': calculate_priority_score(req),
        })

    ranked_requests = run_priority_algorithm([r['request'] for r in eligible_requests])
    ranked_requests_data = []
    for item in ranked_requests[:15]:
        req = item['request']
        distance = next((r['distance'] for r in eligible_requests if r['request'] == req), None)
        ranked_requests_data.append({
            'request':        req,
            'hospital_name':  req.hospital.hospital_name,
            'hospital_address': req.hospital.address,
            'urgency':        item['priority_level'],
            'priority_score': item['priority_score'],
            'distance':       distance,
        })

    # Donation history summary
    history = donor.donation_history.all().order_by('-date_donated')
    total_units = sum([d.units_donated for d in history]) if history else 0

    # ── NEW: Nearby hospitals for dashboard card ─────────────
    nearby_hospitals = []
    if donor.latitude and donor.longitude:
        all_hospitals = HospitalProfile.objects.filter(is_verified=True)
        for hospital in all_hospitals:
            if not (hospital.latitude and hospital.longitude):
                continue
            dist = haversine_distance(
                donor.latitude, donor.longitude,
                hospital.latitude, hospital.longitude
            )
            if dist > 50:
                continue
            # Get the most urgent active blood request for this hospital
            active_req = BloodRequest.objects.filter(
                hospital=hospital, status='pending'
            ).order_by(
                # critical first, then high, medium, low
                '-urgency_level'
            ).first()

            nearby_hospitals.append({
                'hospital_id':   hospital.id,
                'hospital_name': hospital.hospital_name,
                'address':       hospital.address,
                'blood_type':    active_req.blood_type if active_req else '—',
                'units_needed':  active_req.units_needed if active_req else '—',
                'urgency_level': active_req.urgency_level if active_req else 'low',
                'distance':      round(dist, 1),
            })
        nearby_hospitals.sort(key=lambda x: x['distance'])
        nearby_hospitals = nearby_hospitals[:6]   # show top 6 on dashboard
    # ── END NEW ──────────────────────────────────────────────

    context = {
        'donor':               donor,
        'history':             history,
        'total_units':         total_units,
        'ranked_requests':     ranked_requests_data,
        'leaderboard':         leaderboard,
        'active_notifications': active_notifications,
        'past_notifications':  past_notifications,
        'can_donate':          donor.can_donate,
        'days_until_eligible': get_days_until_eligible(donor),
        'lives_saved':         len(history) * 3,
        'max_distance':        max_distance,
        'nearby_hospitals':    nearby_hospitals,   # ← NEW
    }
    return render(request, 'donors/donor_dashboard.html', context)


# ============================================
# DONOR DASHBOARD DATA  (AJAX / JSON endpoint)
# Called by the dashboard JS to populate:
#   - Past notifications accordion
#   - Donation history modal
#   - Donor stats (points, count)
# ============================================
@role_required('donor')
def donor_dashboard_data(request):
    donor = request.user.donor_profile

    # Past notifications
    past_notifs = DonorNotification.objects.filter(
        donor=donor
    ).exclude(status='notified').select_related(
        'blood_request', 'blood_request__hospital'
    ).order_by('-sent_at')[:10]

    notifs_data = []
    for n in past_notifs:
        br = n.blood_request
        notifs_data.append({
            'id':          n.id,
            'hospital':    br.hospital.hospital_name,
            'date':        n.sent_at.strftime('%b %d, %Y'),
            'status':      n.status,
            'blood_group': br.blood_type,
            'units':       br.units_needed,
            'patient':     getattr(br, 'patient_name', '—'),
            'ward':        getattr(br, 'ward', '—'),
            'urgency':     br.urgency_level,
            'distance':    round(n.distance, 2) if n.distance else None,
            'fulfilled_at': n.responded_at.strftime('%b %d, %Y') if n.responded_at else None,
        })

    # Donation history
    history_qs = DonationHistory.objects.filter(
        donor=donor
    ).select_related('hospital').order_by('-date_donated')

    history_data = [
        {
            'date':     h.date_donated.strftime('%b %d, %Y'),
            'hospital': h.hospital.hospital_name if h.hospital else '—',
            'units':    h.units_donated,
            'pts':      POINTS_PER_DONATION,
        }
        for h in history_qs
    ]

    return JsonResponse({
        'past_notifications': notifs_data,
        'donation_history':   history_data,
        'donor_stats': {
            'points':         donor.points,
            'donation_count': donor.donation_count,
            'blood_type':     donor.blood_type,
            'can_donate':     donor.can_donate,
        },
    })


# ============================================
# VIEW NOTIFICATION DETAIL
# ============================================
@role_required('donor')
def view_notification_detail(request, notification_id):
    notification = get_object_or_404(DonorNotification, id=notification_id)

    if notification.donor.user != request.user:
        messages.error(request, "Access denied.")
        return redirect('donor_dashboard')

    notification.is_read = True
    notification.save()

    blood_request = notification.blood_request
    hospital      = blood_request.hospital

    context = {
        'notification': notification,
        'blood_request': blood_request,
        'hospital':      hospital,
        'can_respond':   notification.status == 'notified',
    }
    return render(request, 'donors/notification_detail.html', context)


# ============================================
# ACCEPT BLOOD REQUEST
# ============================================
@role_required('donor')
def accept_blood_request(request, notification_id):
    notification = get_object_or_404(DonorNotification, id=notification_id)

    if notification.donor.user != request.user:
        messages.error(request, "You don't have permission to respond to this notification.")
        return redirect('donor_dashboard')

    if notification.status != 'notified':
        status_messages = {
            'accepted':  "You have already accepted this request.",
            'rejected':  "You have already rejected this request.",
            'cancelled': "This request has been cancelled or fulfilled by another donor.",
        }
        msg = status_messages.get(notification.status, "This notification is no longer active.")
        messages.warning(request, msg)
        return redirect('donor_dashboard')

    if request.method == 'POST':
        donor        = notification.donor
        blood_request = notification.blood_request

        # 1. Update notification
        notification.status        = 'accepted'
        notification.responded_at  = timezone.now()
        notification.response_notes = request.POST.get('notes', '')
        notification.responded     = True
        notification.save()

        # 2. Update BloodRequest status
        blood_request.status = 'fulfilled'
        blood_request.save()

        # 3. Create DonationHistory record
        DonationHistory.objects.create(
            donor=donor,
            hospital=blood_request.hospital,
            blood_request=blood_request,
            units_donated=blood_request.units_needed,
            date_donated=date.today(),
        )

        # 4. Update donor stats + award points
        donor.donation_count    = donor.donation_history.count()
        donor.last_donation_date = date.today()
        donor.points            = (donor.points or 0) + POINTS_PER_DONATION  # ← POINTS AWARDED
        donor.save()

        # 5. Backward-compat DonorResponse record
        DonorResponse.objects.create(
            donor=donor,
            blood_request=blood_request,
            status='accepted',
            response_notes=notification.response_notes,
        )

        # 6. Cancel all other pending notifications for this request
        DonorNotification.objects.filter(
            blood_request=blood_request,
            status__in=['pending', 'notified']
        ).exclude(id=notification_id).update(status='cancelled')

        # 7. Notify hospital (limited info only)
        send_hospital_acceptance_notification(donor, blood_request, notification.distance)

        # 8. Notify admin
        send_admin_acceptance_notification(blood_request, donor, notification)

        messages.success(
            request,
            f"✅ You have accepted the blood request from "
            f"{blood_request.hospital.hospital_name}. "
            f"The hospital has been notified. You earned {POINTS_PER_DONATION} points!"
        )
        return redirect('donor_dashboard')

    context = {
        'notification': notification,
        'blood_request': notification.blood_request,
    }
    return render(request, 'donors/confirm_accept.html', context)


# ============================================
# REJECT BLOOD REQUEST
# ============================================
@role_required('donor')
def reject_blood_request(request, notification_id):
    notification = get_object_or_404(DonorNotification, id=notification_id)

    if notification.donor.user != request.user:
        messages.error(request, "You don't have permission to respond to this notification.")
        return redirect('donor_dashboard')

    if notification.status != 'notified':
        status_messages = {
            'accepted':  "You have already accepted this request.",
            'rejected':  "You have already rejected this request.",
            'cancelled': "This request has been cancelled or fulfilled by another donor.",
        }
        msg = status_messages.get(notification.status, "This notification is no longer active.")
        messages.warning(request, msg)
        return redirect('donor_dashboard')

    if request.method == 'POST':
        rejection_reason = request.POST.get('reason', 'Not specified')
        donor            = notification.donor
        blood_request    = notification.blood_request

        notification.status         = 'rejected'
        notification.responded_at   = timezone.now()
        notification.response_notes = rejection_reason
        notification.responded      = True
        notification.save()

        DonorResponse.objects.create(
            donor=donor,
            blood_request=blood_request,
            status='declined',
            response_notes=rejection_reason,
        )

        send_admin_rejection_notification(blood_request, donor, rejection_reason)

        messages.info(
            request,
            "You have declined the blood request. "
            "Admin has been notified and will contact the next available donor."
        )
        return redirect('donor_dashboard')

    context = {
        'notification': notification,
        'blood_request': notification.blood_request,
    }
    return render(request, 'donors/confirm_reject.html', context)


# ============================================
# FULFILL BLOOD REQUEST  ← NEW
# Donor confirms they have physically donated.
# Awards points, creates history record, emails admin.
# ============================================
@role_required('donor')
def fulfill_blood_request(request, notification_id):
    notification = get_object_or_404(DonorNotification, id=notification_id)

    if notification.donor.user != request.user:
        messages.error(request, "Access denied.")
        return redirect('donor_dashboard')

    if notification.status != 'accepted':
        messages.warning(request, "Only accepted requests can be marked as donated.")
        return redirect('donor_dashboard')

    if request.method == 'POST':
        donor         = notification.donor
        blood_request = notification.blood_request

        # 1. Mark notification fulfilled
        notification.status       = 'fulfilled'
        notification.responded_at = timezone.now()
        notification.save()

        # 2. Mark blood request fulfilled (if not already)
        if blood_request.status != 'fulfilled':
            blood_request.status = 'fulfilled'
            blood_request.save()

        # 3. Create DonationHistory record (only if one doesn't already exist for this request)
        already_logged = DonationHistory.objects.filter(
            donor=donor, blood_request=blood_request
        ).exists()
        if not already_logged:
            DonationHistory.objects.create(
                donor=donor,
                hospital=blood_request.hospital,
                blood_request=blood_request,
                units_donated=blood_request.units_needed,
                date_donated=date.today(),
            )
            # 4. Award points and update donor stats
            donor.donation_count     = donor.donation_history.count()
            donor.last_donation_date = date.today()
            donor.points             = (donor.points or 0) + POINTS_PER_DONATION
            donor.save()

        # 5. Notify admin that physical donation is confirmed
        _send_fulfill_admin_notification(blood_request, donor)

        messages.success(
            request,
            f"✅ Donation confirmed! Thank you for donating to "
            f"{blood_request.hospital.hospital_name}. "
            f"You earned {POINTS_PER_DONATION} points!"
        )
    return redirect('donor_dashboard')


# ============================================
# VIEW BLOOD REQUEST DETAIL
# ============================================
@role_required('donor')
def view_blood_request_detail(request, request_id):
    donor        = request.user.donor_profile
    blood_request = get_object_or_404(BloodRequest, id=request_id)
    is_eligible  = is_donor_eligible(donor, blood_request)

    distance = None
    if (donor.latitude and donor.longitude and
            blood_request.hospital.latitude and blood_request.hospital.longitude):
        distance = haversine_distance(
            donor.latitude, donor.longitude,
            blood_request.hospital.latitude, blood_request.hospital.longitude
        )

    context = {
        'blood_request':    blood_request,
        'hospital':         blood_request.hospital,
        'is_eligible':      is_eligible,
        'distance':         round(distance, 2) if distance is not None else None,
        'priority_score':   calculate_priority_score(blood_request),
        'can_donate':       donor.can_donate,
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
        status_str = "available" if donor.is_available else "unavailable"
        messages.success(request, f"Your status has been updated to {status_str}.")
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
# DONATION HISTORY (full page view)
# ============================================
@role_required('donor')
def donation_history(request):
    donor         = request.user.donor_profile
    history       = DonationHistory.objects.filter(donor=donor).order_by('-date_donated')
    total_donations = history.count()
    total_units   = sum(d.units_donated for d in history) if history else 0

    history_by_year = defaultdict(list)
    for donation in history:
        history_by_year[donation.date_donated.year].append(donation)

    context = {
        'donor':          donor,
        'history':        history,
        'total_donations': total_donations,
        'total_units':    total_units,
        'history_by_year': dict(sorted(history_by_year.items(), reverse=True)),
    }
    return render(request, 'donors/donation_history.html', context)


# ============================================
# VIEW DONOR DETAIL (for hospitals)
# ============================================
@role_required('hospital')
def view_donor_detail(request, donor_id):
    donor            = get_object_or_404(DonorProfile, id=donor_id)
    hospital_profile = getattr(request.user, 'hospitalprofile', None)

    distance = None
    if (hospital_profile and donor.latitude and donor.longitude and
            hospital_profile.latitude and hospital_profile.longitude):
        distance = haversine_distance(
            hospital_profile.latitude, hospital_profile.longitude,
            donor.latitude, donor.longitude
        )

    context = {
        'donor':    donor,
        'distance': round(distance, 2) if distance is not None else None,
        'hospital': hospital_profile,
    }
    return render(request, 'donors/view_donor_detail.html', context)


# ============================================
# FIND NEARBY HOSPITALS
# Supports two modes:
#   A) ?format=json&lat=X&lng=Y  → JSON for dashboard modal (AJAX)
#   B) Normal GET                 → renders nearby_hospitals.html
# ============================================
@role_required('donor')
def find_nearby_hospitals(request):
    donor = request.user.donor_profile

    # Prefer fresh GPS coords from JS, fall back to stored profile coords
    try:
        lat = float(request.GET.get('lat') or donor.latitude)
        lng = float(request.GET.get('lng') or donor.longitude)
    except (TypeError, ValueError):
        lat, lng = None, None

    if not (lat and lng):
        if request.GET.get('format') == 'json':
            return JsonResponse(
                {'error': 'Location not available. Please allow location access in your browser.'},
                status=400
            )
        messages.error(request, "Please update your location in your profile first.")
        return redirect('donor_dashboard')

    # Save fresh coords back to profile if provided by JS
    if request.GET.get('lat'):
        donor.latitude  = lat
        donor.longitude = lng
        donor.save(update_fields=['latitude', 'longitude'])

    all_hospitals = HospitalProfile.objects.filter(is_verified=True)
    nearby = []

    for hospital in all_hospitals:
        if not (hospital.latitude and hospital.longitude):
            continue
        distance = haversine_distance(lat, lng, hospital.latitude, hospital.longitude)
        if distance > 50:
            continue

        active_requests = BloodRequest.objects.filter(hospital=hospital, status='pending')
        compatible      = [r for r in active_requests if is_compatible(donor.blood_type, r.blood_type)]

        nearby.append({
            'hospital':            hospital,
            'distance':            round(distance, 2),
            'total_requests':      active_requests.count(),
            'compatible_requests': len(compatible),
            'blood_needs':         list(
                active_requests.values_list('blood_type', flat=True).distinct()
            ),
        })

    nearby.sort(key=lambda x: x['distance'])
    nearby = nearby[:20]

    # JSON branch — called by dashboard JS modal
    if request.GET.get('format') == 'json':
        return JsonResponse({
            'count':   len(nearby),
            'results': [
                {
                    'id':                  h['hospital'].id,
                    'name':                h['hospital'].hospital_name,
                    'address':             h['hospital'].address,
                    'phone':               getattr(h['hospital'], 'phone', ''),
                    'distance_km':         h['distance'],
                    'active_requests':     h['total_requests'],
                    'compatible_requests': h['compatible_requests'],
                    'blood_needs':         h['blood_needs'],
                }
                for h in nearby
            ]
        })

    # Normal HTML response
    return render(request, 'donors/nearby_hospitals.html', {
        'donor':            donor,
        'nearby_hospitals': nearby,
    })


# ============================================
# MARK NOTIFICATIONS READ
# ============================================
@role_required('donor')
def mark_notification_read(request, notification_id):
    try:
        notification = DonorNotification.objects.get(
            id=notification_id, donor=request.user.donor_profile
        )
        notification.is_read = True
        notification.save()
        messages.success(request, "Notification marked as read.")
    except DonorNotification.DoesNotExist:
        messages.error(request, "Notification not found.")
    return redirect('donor_dashboard')


@role_required('donor')
def mark_all_notifications_read(request):
    DonorNotification.objects.filter(
        donor=request.user.donor_profile, is_read=False
    ).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect('donor_dashboard')


# ============================================
# NOTIFY DONOR (Admin/Hospital triggered)
# ============================================
@role_required('hospital')
def notify_donor(request, donor_id):
    donor = get_object_or_404(DonorProfile, id=donor_id)

    if request.method == 'POST':
        request_id   = request.POST.get('blood_request_id')
        blood_request = get_object_or_404(BloodRequest, id=request_id)

        notification, created = DonorNotification.objects.get_or_create(
            donor=donor,
            blood_request=blood_request,
            defaults={
                'status':      'notified',
                'is_notified': True,
                'notified_at': timezone.now(),
            }
        )

        if created:
            messages.success(request, f"Donor {donor.user.username} has been notified.")
        else:
            messages.warning(request, "This donor was already notified for this request.")
        return redirect('donor_dashboard')

    context = {
        'donor':            donor,
        'pending_requests': BloodRequest.objects.filter(status='pending'),
    }
    return render(request, 'donors/notify_donor.html', context)


# ============================================
# EMAIL HELPERS
# ============================================
def send_hospital_acceptance_notification(donor, blood_request, distance):
    hospital     = blood_request.hospital
    distance_str = f"{distance:.2f}km" if distance else "N/A"

    message = f"""
✅ DONOR ACCEPTED YOUR BLOOD REQUEST!

Request for: {blood_request.patient_name}
Blood Type Required: {blood_request.blood_type}

DONOR DETAILS (Limited Info):
Username: {donor.user.username}
Blood Type: {donor.blood_type}
Distance: {distance_str}

The donor has been notified and will coordinate with you.

Thank you for using LifeLink Nepal!
    """.strip()

    if hospital.user.email:
        try:
            send_mail(
                subject=f"✅ Donor Accepted - Blood Request #{blood_request.id}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[hospital.user.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"❌ Failed to send email to hospital: {e}")


def send_admin_acceptance_notification(blood_request, donor, notification):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    admins       = User.objects.filter(is_superuser=True, is_active=True)
    distance_str = f"{notification.distance:.2f}km" if notification.distance else "N/A"

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
Distance: {distance_str}
Points Awarded: {POINTS_PER_DONATION}

View in admin: {settings.SITE_URL}/admin/hospitals/bloodrequest/{blood_request.id}/change/
    """.strip()

    admin_emails = [a.email for a in admins if a.email]
    if admin_emails:
        try:
            send_mail(
                subject=f"✅ Donor Accepted - Request #{blood_request.id}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=False,
            )
        except Exception as e:
            print(f"❌ Failed to send email to admins: {e}")


def send_admin_rejection_notification(blood_request, donor, reason):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    admins = User.objects.filter(is_superuser=True, is_active=True)

    next_notification = DonorNotification.objects.filter(
        blood_request=blood_request,
        is_notified=False,
        status='pending'
    ).order_by('priority_order').first()

    next_donor_info = (
        f"\nNEXT DONOR: {next_notification.donor.full_name} "
        f"(Priority #{next_notification.priority_order})"
        if next_notification
        else "\n⚠️ NO MORE DONORS AVAILABLE IN QUEUE"
    )

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

ACTION REQUIRED: Please login and click "Notify Next Donor"
Link: {settings.SITE_URL}/admin/hospitals/bloodrequest/{blood_request.id}/change/
    """.strip()

    admin_emails = [a.email for a in admins if a.email]
    if admin_emails:
        try:
            send_mail(
                subject=f"❌ Donor Rejected - Action Required - Request #{blood_request.id}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=False,
            )
        except Exception as e:
            print(f"❌ Failed to send email to admins: {e}")


# ── NEW: Admin email for physical donation confirmed ─────────
def _send_fulfill_admin_notification(blood_request, donor):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    admins = User.objects.filter(is_superuser=True, is_active=True)

    message = f"""
🩸 PHYSICAL DONATION CONFIRMED BY DONOR

Request ID: #{blood_request.id}
Hospital: {blood_request.hospital.hospital_name}
Patient: {blood_request.patient_name}
Blood Type: {blood_request.blood_type}
Units: {blood_request.units_needed}

DONATED BY:
Donor: {donor.full_name}
Username: {donor.user.username}
Phone: {donor.phone}
Points Awarded: {POINTS_PER_DONATION}
Date: {date.today().strftime('%b %d, %Y')}

Please verify with the hospital and update records as needed.
View in admin: {settings.SITE_URL}/admin/hospitals/bloodrequest/{blood_request.id}/change/
    """.strip()

    admin_emails = [a.email for a in admins if a.email]
    if admin_emails:
        try:
            send_mail(
                subject=f"🩸 Donation Fulfilled - Request #{blood_request.id} - Verify Required",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=False,
            )
        except Exception as e:
            print(f"❌ Failed to send fulfill email to admins: {e}")


# ============================================
# HELPER FUNCTIONS
# ============================================
def get_days_until_eligible(donor):
    if not donor.last_donation_date:
        return 0
    days_since = (date.today() - donor.last_donation_date).days
    return max(0, 90 - days_since)


def calculate_priority_score(blood_request):
    urgency_scores = {'critical': 3, 'high': 2, 'medium': 1, 'low': 0}
    return urgency_scores.get(blood_request.urgency_level, 0)