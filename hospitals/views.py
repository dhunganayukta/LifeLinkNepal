# hospitals/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from accounts.decorators import role_required
from .models import BloodRequest, HospitalProfile
from donors.models import DonorProfile, DonorNotification, DonationHistory
from algorithms.blood_compatibility import get_compatible_donors
from algorithms.haversine import haversine_distance
from algorithms.mcdm import rank_donors_mcdm
from algorithms.priority import run_priority_algorithm
from algorithms.eligibility import is_donor_eligible
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import date

POINTS_PER_DONATION = 50

FALLBACK_PRIORITY = {
    'A+':  ['A-', 'O+', 'O-'],
    'A-':  ['O-'],
    'B+':  ['B-', 'O+', 'O-'],
    'B-':  ['O-'],
    'AB+': ['A+', 'A-', 'B+', 'B-', 'O+', 'O-'],
    'AB-': ['A-', 'B-', 'O-'],
    'O+':  ['O-'],
    'O-':  [],
}


# ============================================
# DASHBOARD
# ============================================
@role_required('hospital')
def hospital_dashboard(request):
    hospital_profile = request.user.hospitalprofile

    blood_requests  = BloodRequest.objects.filter(hospital=hospital_profile).order_by('-created_at')
    ranked_requests = run_priority_algorithm(blood_requests)

    pending_verification = blood_requests.filter(status='donor_confirmed').count()

    context = {
        'hospital':             hospital_profile,
        'ranked_requests':      ranked_requests,
        'total_requests':       blood_requests.count(),
        'pending_count':        blood_requests.filter(status='pending').count(),
        'fulfilled_count':      blood_requests.filter(status='fulfilled').count(),
        'critical_count':       len([r for r in ranked_requests if r['priority_level'] == 'critical']),
        'pending_verification': pending_verification,
    }
    return render(request, 'hospitals/hospital_dashboard.html', context)


# ============================================
# CREATE BLOOD REQUEST
# ============================================
@role_required('hospital')
def create_blood_request(request):
    hospital_profile = request.user.hospitalprofile

    if request.method == 'POST':
        patient_name  = request.POST.get('patient_name')
        patient_age   = request.POST.get('patient_age')
        blood_type    = request.POST.get('blood_type')
        units_needed  = int(request.POST.get('units_needed', 1))
        urgency_level = request.POST.get('urgency_level')
        condition     = request.POST.get('condition', '')
        notes         = request.POST.get('notes', '')

        if not all([patient_name, blood_type, urgency_level]):
            messages.error(request, "Please fill in all required fields.")
            return render(request, 'hospitals/emergency.html', {'hospital': hospital_profile})

        try:
            blood_request = BloodRequest.objects.create(
                hospital      = hospital_profile,
                patient_name  = patient_name,
                patient_age   = int(patient_age) if patient_age else None,
                blood_type    = blood_type,
                units_needed  = units_needed,
                urgency_level = urgency_level,
                condition     = condition,
                notes         = notes,
                status        = 'pending'
            )

            donors          = DonorProfile.objects.filter(is_available=True, user__is_active=True)
            eligible_donors = [d for d in donors if is_donor_eligible(d, blood_request, max_distance=50)]

            used_fallback       = False
            fallback_types_used = []

            if not eligible_donors:
                fallback_types = FALLBACK_PRIORITY.get(blood_type, [])
                if fallback_types:
                    fallback_donors = DonorProfile.objects.filter(
                        is_available=True, user__is_active=True, blood_type__in=fallback_types
                    )
                    eligible_donors     = [d for d in fallback_donors if is_donor_eligible(d, blood_request, max_distance=50)]
                    used_fallback       = True
                    fallback_types_used = sorted(set(d.blood_type for d in eligible_donors))

            if not eligible_donors:
                messages.warning(request, f"⚠ Blood request created for {blood_type}, but no compatible donors are available within 50km. Admin has been notified.")
                send_admin_notification(blood_request, donor_count=0)
                return redirect('hospital_dashboard')

            distances = {d.id: (d.distance if d.distance is not None else 999.0) for d in eligible_donors}
            ranked_donors = rank_donors_mcdm(
                eligible_donors,
                hospital_profile.latitude  or 0,
                hospital_profile.longitude or 0,
                distances,
                blood_type
            )
            ranked_donors.sort(key=lambda x: distances.get(x[0].id) if distances.get(x[0].id) is not None else 999)

            for priority_order, (donor, mcdm_score) in enumerate(ranked_donors, start=1):
                is_first = (priority_order == 1)
                DonorNotification.objects.create(
                    donor          = donor,
                    blood_request  = blood_request,
                    match_score    = mcdm_score,
                    distance       = distances.get(donor.id, 0),
                    priority_order = priority_order,
                    status         = 'notified' if is_first else 'pending',
                    is_notified    = is_first,
                    notified_at    = timezone.now() if is_first else None,
                )

            first_donor, _ = ranked_donors[0]
            send_donor_notification_email(first_donor, blood_request, distances.get(first_donor.id))
            send_admin_notification(blood_request, len(ranked_donors))

            if used_fallback:
                messages.warning(request, f"⚠ No exact {blood_type} donors available. Found {len(ranked_donors)} donor(s) with compatible types: {', '.join(fallback_types_used)}. Top donor notified automatically.")
            else:
                messages.success(request, f"✅ Blood request created! {len(ranked_donors)} eligible donors found. Top donor notified automatically.")

            return redirect('view_blood_request', request_id=blood_request.id)

        except Exception as e:
            messages.error(request, f"Error creating blood request: {str(e)}")

    return render(request, 'hospitals/emergency.html', {'hospital': hospital_profile})


# ============================================
# NOTIFY NEXT DONOR IN QUEUE
# ============================================
def notify_next_donor(blood_request):
    next_notification = DonorNotification.objects.filter(
        blood_request=blood_request,
        status='pending',
        is_notified=False,
    ).order_by('priority_order').first()

    if not next_notification:
        send_admin_notification(blood_request, donor_count=0)
        return None

    next_notification.status      = 'notified'
    next_notification.is_notified = True
    next_notification.notified_at = timezone.now()
    next_notification.save()

    send_donor_notification_email(next_notification.donor, blood_request, next_notification.distance)
    return next_notification


# ============================================
# VIEW ALL BLOOD REQUESTS
# ============================================
@role_required('hospital')
def all_blood_requests(request):
    hospital_profile = request.user.hospitalprofile
    status           = request.GET.get('status', 'all')

    blood_requests = BloodRequest.objects.filter(hospital=hospital_profile).order_by('-created_at')

    if status and status != 'all':
        allowed = ['pending', 'accepted', 'donor_confirmed', 'fulfilled', 'cancelled', 'mismatch']
        if status in allowed:
            blood_requests = blood_requests.filter(status=status)

    ranked_requests = run_priority_algorithm(blood_requests)

    context = {
        'hospital':        hospital_profile,
        'ranked_requests': ranked_requests,
        'status':          status,
    }
    return render(request, 'hospitals/all_blood_requests.html', context)


# ============================================
# VIEW SINGLE BLOOD REQUEST
# ============================================
@login_required
def view_blood_request(request, request_id):
    if request.user.is_superuser:
        blood_request = get_object_or_404(BloodRequest, id=request_id)
    else:
        if not hasattr(request.user, 'hospitalprofile'):
            messages.error(request, "Access denied.")
            return redirect('home')
        blood_request = get_object_or_404(BloodRequest, id=request_id, hospital=request.user.hospitalprofile)

    notifications = DonorNotification.objects.filter(
        blood_request=blood_request
    ).select_related('donor', 'donor__user').order_by('priority_order')

    donor_data = []
    for notification in notifications[:20]:
        donor_data.append({
            'username':   notification.donor.user.username,
            'blood_type': notification.donor.blood_type,
            'distance':   round(notification.distance, 2) if notification.distance else None,
            'status':     notification.get_status_display(),
        })

    accepted_notification = notifications.filter(status__in=['accepted', 'donor_confirmed', 'fulfilled']).first()
    accepted_donor_info   = None
    if accepted_notification:
        accepted_donor_info = {
            'username':   accepted_notification.donor.user.username,
            'blood_type': accepted_notification.donor.blood_type,
            'distance':   round(accepted_notification.distance, 2) if accepted_notification.distance else None,
            'status':     accepted_notification.status,
        }

    context = {
        'blood_request':      blood_request,
        'donor_data':         donor_data,
        'total_donors_found': len(donor_data),
        'accepted_donor':     accepted_donor_info,
        'can_mark_fulfilled': blood_request.status == 'donor_confirmed',
        'donor_confirmed':    blood_request.status == 'donor_confirmed',
    }
    return render(request, 'hospitals/blood_request.html', context)


# ============================================
# MARK FULFILLED
# ✅ DUAL CONFIRMATION — Step 2 of 2
# Also handles admin resolution of mismatches
# ============================================
@login_required
@require_POST
def mark_fulfilled(request, request_id):
    if request.user.is_superuser:
        blood_request = get_object_or_404(BloodRequest, id=request_id)
    else:
        if not hasattr(request.user, 'hospitalprofile'):
            messages.error(request, "Access denied.")
            return redirect('home')
        blood_request = get_object_or_404(BloodRequest, id=request_id, hospital=request.user.hospitalprofile)

    force_mismatch = request.POST.get('force_mismatch') == '1'
    admin_resolve  = request.POST.get('admin_resolve')  # 'award' or 'void'

    notification = DonorNotification.objects.filter(
        blood_request=blood_request,
        status__in=['accepted', 'donor_confirmed', 'mismatch'],
    ).first()

    donor = notification.donor if notification else None

    # ── ADMIN RESOLUTION ─────────────────────────────────────────────────────
    if admin_resolve and request.user.is_superuser:

        if admin_resolve == 'award' and donor:
            blood_request.status = 'fulfilled'
            blood_request.save()
            if notification:
                notification.status = 'fulfilled'
                notification.save()
            DonationHistory.objects.filter(
                donor=donor, blood_request=blood_request
            ).update(is_verified=True)
            donor.donation_count     = donor.donation_history.filter(is_verified=True).count()
            donor.last_donation_date = date.today()
            donor.points             = (donor.points or 0) + POINTS_PER_DONATION
            donor.save()
            _notify_donor_points_awarded(donor, blood_request)
            _send_fulfill_admin_notification(blood_request, donor, verified=True)
            messages.success(request, f"✅ Admin resolved: Donation confirmed. @{donor.user.username} awarded {POINTS_PER_DONATION} points.")

        elif admin_resolve == 'void' and donor:
            # Cancel this donor's notification and reopen request for next donor
            if notification:
                notification.status = 'cancelled'
                notification.save()

            # Reset request to pending so next donor can pick it up
            blood_request.status = 'pending'
            blood_request.save()

            # Notify the voided donor
            _send_void_notification(blood_request, donor)

            # Notify next donor in queue
            next_notification = notify_next_donor(blood_request)
            if next_notification:
                messages.warning(
                    request,
                    f"⚠ Admin resolved: Donation voided. @{donor.user.username} removed. "
                    f"Next donor @{next_notification.donor.user.username} has been notified."
                )
            else:
                messages.warning(
                    request,
                    f"⚠ Admin resolved: Donation voided. @{donor.user.username} removed. "
                    f"No more donors in queue — request is pending. Consider creating a new request."
                )

        else:
            messages.error(request, "Invalid admin resolution or no donor found.")

    # ── CASE A: donor_confirmed + hospital says NO ────────────────────────────
    elif blood_request.status == 'donor_confirmed' and force_mismatch and donor:
        blood_request.status = 'mismatch'
        blood_request.save()
        if notification:
            notification.status = 'mismatch'
            notification.save()
        _send_mismatch_admin_notification(blood_request, donor, confirmed_by='hospital_rejected')
        messages.warning(
            request,
            f"⚠ Flagged as mismatch. @{donor.user.username} confirmed donation but you marked it as NOT received. "
            f"Admin has been alerted. Points are held pending investigation."
        )

    # ── CASE B: donor_confirmed + hospital says YES ───────────────────────────
    elif blood_request.status == 'donor_confirmed' and not force_mismatch and donor:
        blood_request.status = 'fulfilled'
        blood_request.save()
        notification.status = 'fulfilled'
        notification.save()
        DonationHistory.objects.filter(
            donor=donor, blood_request=blood_request
        ).update(is_verified=True)
        donor.donation_count     = donor.donation_history.filter(is_verified=True).count()
        donor.last_donation_date = date.today()
        donor.points             = (donor.points or 0) + POINTS_PER_DONATION
        donor.save()
        DonorNotification.objects.filter(
            blood_request=blood_request, status__in=['pending', 'notified']
        ).update(status='cancelled')
        _notify_donor_points_awarded(donor, blood_request)
        _send_fulfill_admin_notification(blood_request, donor, verified=True)
        messages.success(
            request,
            f"✅ Donation verified! Request for {blood_request.patient_name} fulfilled. "
            f"@{donor.user.username} awarded {POINTS_PER_DONATION} points."
        )

    # ── CASE C: accepted but donor never confirmed ────────────────────────────
    elif blood_request.status == 'accepted' and donor:
        blood_request.status = 'mismatch'
        blood_request.save()
        if notification:
            notification.status = 'mismatch'
            notification.save()
        _send_mismatch_admin_notification(blood_request, donor, confirmed_by='hospital')
        messages.warning(
            request,
            f"⚠ Marked on your side, but @{donor.user.username} has NOT clicked 'I Have Donated' yet. "
            f"Admin has been alerted. Points are held until the donor confirms."
        )

    else:
        messages.info(request, "This request has already been processed.")

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    return redirect(next_url or 'hospital_dashboard')


# ============================================
# CANCEL REQUEST
# ============================================
@role_required('hospital')
def cancel_request(request, request_id):
    blood_request = get_object_or_404(BloodRequest, id=request_id, hospital=request.user.hospitalprofile)
    blood_request.status = 'cancelled'
    blood_request.save()

    DonorNotification.objects.filter(
        blood_request=blood_request, status__in=['pending', 'notified']
    ).update(status='cancelled')

    messages.info(request, "Blood request has been cancelled.")
    return redirect('hospital_dashboard')


# ============================================
# DONOR MANAGEMENT
# ============================================
@role_required('hospital')
def hospital_donors(request):
    hospital_profile  = request.user.hospitalprofile
    blood_type_filter = request.GET.get('blood_type', '')

    max_distance_param = request.GET.get('max_distance', '')
    try:
        max_distance = int(max_distance_param) if max_distance_param else 50
        max_distance = max(1, min(500, max_distance))
    except (ValueError, TypeError):
        max_distance = 50

    donors = DonorProfile.objects.filter(is_available=True, user__is_active=True)
    if blood_type_filter:
        donors = donors.filter(blood_type=blood_type_filter)

    hospital_has_location = hospital_profile.latitude is not None and hospital_profile.longitude is not None
    donor_list = []

    if hospital_has_location:
        for donor in donors:
            if donor.latitude is not None and donor.longitude is not None:
                distance = haversine_distance(hospital_profile.latitude, hospital_profile.longitude, donor.latitude, donor.longitude)
                if distance <= max_distance:
                    donor_list.append({'username': donor.user.username, 'blood_type': donor.blood_type, 'distance': round(distance, 2)})
        donor_list.sort(key=lambda x: x['distance'])
    else:
        for donor in donors:
            donor_list.append({'username': donor.user.username, 'blood_type': donor.blood_type, 'distance': None})

    context = {
        'hospital':              hospital_profile,
        'donor_list':            donor_list,
        'blood_type_filter':     blood_type_filter,
        'max_distance':          max_distance,
        'hospital_has_location': hospital_has_location,
        'blood_types':           ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],
    }
    return render(request, 'hospitals/hospital_donors.html', context)


# ============================================
# HOSPITAL PROFILE
# ============================================
@role_required('hospital')
def hospital_profile(request):
    return render(request, 'hospitals/hospital_profile.html', {'hospital': request.user.hospitalprofile})


@role_required('hospital')
def edit_hospital_profile(request):
    hospital_profile = request.user.hospitalprofile

    if request.method == 'POST':
        old_address = hospital_profile.address

        hospital_profile.hospital_name  = request.POST.get('hospital_name',  hospital_profile.hospital_name)
        hospital_profile.phone          = request.POST.get('phone',           hospital_profile.phone)
        hospital_profile.address        = request.POST.get('address',         hospital_profile.address)
        hospital_profile.license_number = request.POST.get('license_number',  hospital_profile.license_number)

        if hospital_profile.address != old_address:
            try:
                from geopy.geocoders import Nominatim
                from geopy.exc import GeocoderTimedOut, GeocoderServiceError
                geolocator = Nominatim(user_agent="lifelink_nepal")
                location   = geolocator.geocode(hospital_profile.address + ", Nepal", timeout=10)
                if location:
                    hospital_profile.latitude  = location.latitude
                    hospital_profile.longitude = location.longitude
                    messages.success(request, f"✅ Profile updated! Coordinates set: {location.latitude:.4f}, {location.longitude:.4f}")
                else:
                    messages.warning(request, "⚠️ Profile updated, but couldn't find exact coordinates.")
            except (GeocoderTimedOut, GeocoderServiceError):
                messages.warning(request, "⚠️ Profile updated, but geocoding service temporarily unavailable.")
            except Exception as e:
                messages.warning(request, f"⚠️ Profile updated, but geocoding error: {str(e)}")
        else:
            messages.success(request, "✅ Profile updated successfully.")

        hospital_profile.save()
        return redirect('hospital_profile')

    return render(request, 'hospitals/edit_hospital_profile.html', {'hospital': hospital_profile})


# ============================================
# EMAIL HELPERS
# ============================================
def send_donor_notification_email(donor, blood_request, distance):
    from django.core.mail import send_mail
    from django.conf import settings

    distance_str = f"{distance:.1f}km away" if distance else "nearby"
    message = f"""
🩸 URGENT BLOOD REQUEST — ACTION NEEDED

Dear {donor.full_name},

Hospital    : {blood_request.hospital.hospital_name}
Blood Type  : {blood_request.blood_type}
Units Needed: {blood_request.units_needed}
Urgency     : {blood_request.urgency_level.upper()}
Distance    : {distance_str}

Please log in and ACCEPT or REJECT this request:
{settings.SITE_URL}/donor/dashboard/

Thank you for saving lives 🙏
— LifeLink Nepal
    """.strip()

    if donor.user.email:
        try:
            send_mail(
                subject=f"🩸 Urgent: {blood_request.blood_type} blood needed at {blood_request.hospital.hospital_name}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[donor.user.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"❌ Email failed for donor {donor.full_name}: {e}")


def send_admin_notification(blood_request, donor_count):
    from django.contrib.auth import get_user_model
    from django.core.mail import send_mail
    from django.conf import settings
    User   = get_user_model()
    admins = User.objects.filter(is_superuser=True, is_active=True)

    if donor_count == 0:
        subject    = f"🚨 NO DONORS FOUND — Request #{blood_request.id} Needs Manual Action"
        donor_line = "⚠ NO compatible donors found within 50km. Please contact nearby blood banks."
    else:
        subject    = f"🚨 URGENT: New Blood Request #{blood_request.id} - {blood_request.blood_type}"
        donor_line = f"{donor_count} eligible donor(s) queued. Top donor notified automatically."

    message = f"""
NEW BLOOD REQUEST

Hospital    : {blood_request.hospital.hospital_name}
Patient     : {blood_request.patient_name}
Blood Type  : {blood_request.blood_type}
Units Needed: {blood_request.units_needed}
Urgency     : {blood_request.urgency_level.upper()}

{donor_line}

Admin Panel: {settings.SITE_URL}/admin/hospitals/bloodrequest/{blood_request.id}/change/
    """.strip()

    admin_emails = [a.email for a in admins if a.email]
    if admin_emails:
        send_mail(subject=subject, message=message, from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=admin_emails, fail_silently=True)

    print(f"📧 Admin notified for request #{blood_request.id} — {donor_count} donors")
    return True


def send_hospital_acceptance_notification(donor, blood_request, distance):
    from django.core.mail import send_mail
    from django.conf import settings

    hospital     = blood_request.hospital
    distance_str = f"{distance:.2f}km" if distance else "N/A"
    message = f"""
✅ DONOR ACCEPTED YOUR BLOOD REQUEST!

Request for : {blood_request.patient_name}
Blood Type  : {blood_request.blood_type}
Donor       : {donor.user.username} ({donor.blood_type})
Distance    : {distance_str}

The donor is on their way. When they arrive and donate,
they will mark it complete — you will then receive a
verification request. Please verify promptly to release their reward points.

Thank you for using LifeLink Nepal!
    """.strip()

    if hospital.user.email:
        send_mail(subject=f"✅ Donor Accepted - Blood Request #{blood_request.id}", message=message, from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[hospital.user.email], fail_silently=True)


def _notify_donor_points_awarded(donor, blood_request):
    from django.core.mail import send_mail
    from django.conf import settings

    message = f"""
🎉 YOUR DONATION HAS BEEN VERIFIED!

Hospital   : {blood_request.hospital.hospital_name}
Patient    : {blood_request.patient_name}
Blood Type : {blood_request.blood_type}

{POINTS_PER_DONATION} points have been added to your account.
Thank you for saving a life! 🙏

{settings.SITE_URL}/donor/dashboard/
    """.strip()

    if donor.user.email:
        try:
            send_mail(
                subject=f"🎉 Donation Verified — {POINTS_PER_DONATION} Points Awarded!",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[donor.user.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"❌ Failed to notify donor of points: {e}")


def _send_void_notification(blood_request, donor):
    from django.core.mail import send_mail
    from django.conf import settings

    if donor.user.email:
        try:
            send_mail(
                subject=f"Donation Case #{blood_request.id} — Resolved by Admin",
                message=f"""
Dear {donor.full_name},

After investigation, admin has determined the donation for the following request did not occur:
Hospital   : {blood_request.hospital.hospital_name}
Blood Type : {blood_request.blood_type}
Date       : {date.today().strftime('%b %d, %Y')}

Your assignment to this request has been removed. No points were awarded.
The next donor in queue has been notified to fulfil this request.

If you believe this is an error, please contact support.

— LifeLink Nepal
                """.strip(),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[donor.user.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"❌ Failed to send void notification: {e}")


def _send_mismatch_admin_notification(blood_request, donor, confirmed_by):
    from django.contrib.auth import get_user_model
    from django.core.mail import send_mail
    from django.conf import settings
    User   = get_user_model()
    admins = User.objects.filter(is_superuser=True, is_active=True)

    if confirmed_by == 'hospital':
        confirmed_line   = "HOSPITAL ✅ (hospital said YES, donor never confirmed)"
        unconfirmed_line = "DONOR ❌ (never clicked 'I Have Donated')"
    elif confirmed_by == 'hospital_rejected':
        confirmed_line   = "DONOR ✅ (donor said YES)"
        unconfirmed_line = "HOSPITAL ❌ (hospital says donation did NOT happen)"
    else:
        confirmed_line   = f"{confirmed_by.upper()} ✅"
        unconfirmed_line = "OTHER SIDE ❌"

    message = f"""
⚠ DONATION MISMATCH — MANUAL REVIEW REQUIRED

Request ID : #{blood_request.id}
Hospital   : {blood_request.hospital.hospital_name}
Patient    : {blood_request.patient_name}
Blood Type : {blood_request.blood_type}
Donor      : {donor.full_name} ({donor.user.username})

{confirmed_line}
{unconfirmed_line}

Points are ON HOLD until both sides confirm.
Please investigate and resolve manually.

Admin Panel: {settings.SITE_URL}/admin/hospitals/bloodrequest/{blood_request.id}/change/
    """.strip()

    admin_emails = [a.email for a in admins if a.email]
    if admin_emails:
        try:
            send_mail(
                subject=f"⚠ Donation Mismatch — Request #{blood_request.id} Needs Review",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=True,
            )
        except Exception as e:
            print(f"❌ Failed to send mismatch alert: {e}")


def _send_fulfill_admin_notification(blood_request, donor, verified=False):
    from django.contrib.auth import get_user_model
    from django.core.mail import send_mail
    from django.conf import settings
    User   = get_user_model()
    admins = User.objects.filter(is_superuser=True, is_active=True)

    status_line = "✅ DUAL CONFIRMED — Points awarded." if verified else "⚠ Awaiting dual confirmation."
    message = f"""
🩸 DONATION FULFILLED

Request ID : #{blood_request.id}
Hospital   : {blood_request.hospital.hospital_name}
Patient    : {blood_request.patient_name}
Blood Type : {blood_request.blood_type}
Donor      : {donor.full_name} ({donor.user.username})
Date       : {date.today().strftime('%b %d, %Y')}
{status_line}

Admin Panel: {settings.SITE_URL}/admin/hospitals/bloodrequest/{blood_request.id}/change/
    """.strip()

    admin_emails = [a.email for a in admins if a.email]
    if admin_emails:
        try:
            send_mail(
                subject=f"🩸 Donation Fulfilled - Request #{blood_request.id}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=True,
            )
        except Exception as e:
            print(f"❌ Failed to send admin notification: {e}")