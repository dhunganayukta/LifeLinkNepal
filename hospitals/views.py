# hospitals/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from accounts.decorators import role_required
from .models import BloodRequest, HospitalProfile
from donors.models import DonorProfile, DonorNotification
from algorithms.blood_compatibility import get_compatible_donors
from algorithms.haversine import haversine_distance
from algorithms.mcdm import rank_donors_mcdm
from algorithms.priority import run_priority_algorithm
from algorithms.eligibility import is_donor_eligible
from django.utils import timezone
from django.views.decorators.http import require_POST


# ============================================
# DASHBOARD
# ============================================
@role_required('hospital')
def hospital_dashboard(request):
    hospital_profile = request.user.hospitalprofile

    blood_requests = BloodRequest.objects.filter(
        hospital=hospital_profile
    ).order_by('-created_at')

    ranked_requests = run_priority_algorithm(blood_requests)

    context = {
        'hospital': hospital_profile,
        'ranked_requests': ranked_requests,
        'total_requests': blood_requests.count(),
        'pending_count': blood_requests.filter(status='pending').count(),
        'fulfilled_count': blood_requests.filter(status='fulfilled').count(),
        'critical_count': len([r for r in ranked_requests if r['priority_level'] == 'critical']),
    }
    return render(request, 'hospitals/hospital_dashboard.html', context)


# ============================================
# CREATE BLOOD REQUEST
# ============================================
@role_required('hospital')
def create_blood_request(request):
    hospital_profile = request.user.hospitalprofile

    if request.method == 'POST':
        patient_name = request.POST.get('patient_name')
        patient_age = request.POST.get('patient_age')
        blood_type = request.POST.get('blood_type')
        units_needed = int(request.POST.get('units_needed', 1))
        urgency_level = request.POST.get('urgency_level')
        condition = request.POST.get('condition', '')
        notes = request.POST.get('notes', '')

        if not all([patient_name, blood_type, urgency_level]):
            messages.error(request, "Please fill in all required fields.")
            return render(request, 'hospitals/emergency.html', {'hospital': hospital_profile})

        try:
            blood_request = BloodRequest.objects.create(
                hospital=hospital_profile,
                patient_name=patient_name,
                patient_age=int(patient_age) if patient_age else None,
                blood_type=blood_type,
                units_needed=units_needed,
                urgency_level=urgency_level,
                condition=condition,
                notes=notes,
                status='pending'
            )

            donors = DonorProfile.objects.filter(is_available=True, user__is_active=True)
            eligible_donors = [d for d in donors if is_donor_eligible(d, blood_request, max_distance=50)]

            if not eligible_donors:
                messages.warning(
                    request,
                    f"Blood request created, but no eligible donors found within 50km. "
                    f"Admin will be notified."
                )
                send_admin_notification(blood_request, 0)
                return redirect('hospital_dashboard')

            distances = {d.id: (d.distance if d.distance is not None else 999.0) for d in eligible_donors}
            ranked_donors = rank_donors_mcdm(
                eligible_donors,
                hospital_profile.latitude or 0,
                hospital_profile.longitude or 0,
                distances,
                blood_type
            )

            ranked_donors.sort(key=lambda x: distances.get(x[0].id) if distances.get(x[0].id) is not None else 999)

            for priority_order, (donor, mcdm_score) in enumerate(ranked_donors, start=1):
                DonorNotification.objects.create(
                    donor=donor,
                    blood_request=blood_request,
                    match_score=mcdm_score,
                    distance=distances.get(donor.id, 0),
                    is_notified=False,
                    priority_order=priority_order,
                    status='pending'
                )

            send_admin_notification(blood_request, len(ranked_donors))

            messages.success(
                request,
                f"✅ Emergency blood request created successfully! "
                f"{len(ranked_donors)} eligible donors found. "
                f"Admin has been notified and will manage donor notifications. "
                f"You will be notified when a donor accepts."
            )
            return redirect('view_blood_request', request_id=blood_request.id)

        except Exception as e:
            messages.error(request, f"Error creating blood request: {str(e)}")

    return render(request, 'hospitals/emergency.html', {'hospital': hospital_profile})


# ============================================
# VIEW ALL BLOOD REQUESTS
# ============================================
@role_required('hospital')
def all_blood_requests(request):
    hospital_profile = request.user.hospitalprofile
    status = request.GET.get('status', 'all')

    blood_requests = BloodRequest.objects.filter(hospital=hospital_profile).order_by('-created_at')
    if status and status != 'all':
        allowed = ['pending', 'fulfilled', 'cancelled', 'matched', 'completed']
        if status in allowed:
            blood_requests = blood_requests.filter(status=status)

    ranked_requests = run_priority_algorithm(blood_requests)
    context = {
        'hospital': hospital_profile,
        'ranked_requests': ranked_requests,
        'status': status,
    }
    return render(request, 'hospitals/all_blood_requests.html', context)


# ============================================
# VIEW SINGLE BLOOD REQUEST
# ============================================
@role_required('hospital')
def view_blood_request(request, request_id):
    blood_request = get_object_or_404(BloodRequest, id=request_id, hospital=request.user.hospitalprofile)

    notifications = DonorNotification.objects.filter(
        blood_request=blood_request
    ).select_related('donor', 'donor__user').order_by('priority_order')

    donor_data = []
    for notification in notifications[:20]:
        donor_data.append({
            'username': notification.donor.user.username,
            'blood_type': notification.donor.blood_type,
            'distance': round(notification.distance, 2) if notification.distance else None,
            'status': notification.get_status_display(),
        })

    accepted_notification = notifications.filter(status='accepted').first()
    accepted_donor_info = None
    if accepted_notification:
        accepted_donor_info = {
            'username': accepted_notification.donor.user.username,
            'blood_type': accepted_notification.donor.blood_type,
            'distance': round(accepted_notification.distance, 2) if accepted_notification.distance else None,
        }

    context = {
        'blood_request': blood_request,
        'donor_data': donor_data,
        'total_donors_found': len(donor_data),
        'accepted_donor': accepted_donor_info,
    }
    return render(request, 'hospitals/blood_request.html', context)


# ============================================
# MARK FULFILLED / CANCEL
# ============================================
@role_required('hospital')
@require_POST
def mark_fulfilled(request, request_id):
    blood_request = get_object_or_404(BloodRequest, id=request_id, hospital=request.user.hospitalprofile)
    blood_request.status = 'fulfilled'
    blood_request.save()

    DonorNotification.objects.filter(
        blood_request=blood_request,
        status__in=['pending', 'notified']
    ).update(status='cancelled')

    messages.success(request, f"Request for {blood_request.patient_name} marked as fulfilled.")
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('hospital_dashboard')


@role_required('hospital')
def cancel_request(request, request_id):
    blood_request = get_object_or_404(BloodRequest, id=request_id, hospital=request.user.hospitalprofile)
    blood_request.status = 'cancelled'
    blood_request.save()

    DonorNotification.objects.filter(
        blood_request=blood_request,
        status__in=['pending', 'notified']
    ).update(status='cancelled')

    messages.info(request, "Blood request has been cancelled.")
    return redirect('hospital_dashboard')


# ============================================
# DONOR MANAGEMENT (RESTRICTED - PRIVACY PROTECTED)
# ============================================
@role_required('hospital')
def hospital_donors(request):
    """
    Hospital sees ONLY: username, blood type, distance.
    No full name, phone, email, address, or any personal info.
    """
    hospital_profile = request.user.hospitalprofile
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

    hospital_has_location = (
        hospital_profile.latitude is not None
        and hospital_profile.longitude is not None
    )

    donor_list = []

    if hospital_has_location:
        for donor in donors:
            if donor.latitude is not None and donor.longitude is not None:
                distance = haversine_distance(
                    hospital_profile.latitude,
                    hospital_profile.longitude,
                    donor.latitude,
                    donor.longitude,
                )
                if distance <= max_distance:
                    donor_list.append({
                        'username': donor.user.username,
                        'blood_type': donor.blood_type,
                        'distance': round(distance, 2),
                    })
        donor_list.sort(key=lambda x: x['distance'])
    else:
        for donor in donors:
            donor_list.append({
                'username': donor.user.username,
                'blood_type': donor.blood_type,
                'distance': None,
            })

    context = {
        'hospital': hospital_profile,
        'donor_list': donor_list,
        'blood_type_filter': blood_type_filter,
        'max_distance': max_distance,
        'hospital_has_location': hospital_has_location,
        # ✅ FIX: pass blood types to template instead of using |split filter
        'blood_types': ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],
    }
    return render(request, 'hospitals/hospital_donors.html', context)


# ============================================
# HOSPITAL PROFILE
# ============================================
@role_required('hospital')
def hospital_profile(request):
    hospital_profile = request.user.hospitalprofile
    context = {'hospital': hospital_profile}
    return render(request, 'hospitals/hospital_profile.html', context)


@role_required('hospital')
def edit_hospital_profile(request):
    hospital_profile = request.user.hospitalprofile

    if request.method == 'POST':
        old_address = hospital_profile.address

        hospital_profile.hospital_name = request.POST.get('hospital_name', hospital_profile.hospital_name)
        hospital_profile.phone = request.POST.get('phone', hospital_profile.phone)
        hospital_profile.address = request.POST.get('address', hospital_profile.address)
        hospital_profile.license_number = request.POST.get('license_number', hospital_profile.license_number)

        if hospital_profile.address != old_address:
            try:
                from geopy.geocoders import Nominatim
                from geopy.exc import GeocoderTimedOut, GeocoderServiceError

                geolocator = Nominatim(user_agent="lifelink_nepal")
                location = geolocator.geocode(hospital_profile.address + ", Nepal", timeout=10)

                if location:
                    hospital_profile.latitude = location.latitude
                    hospital_profile.longitude = location.longitude
                    messages.success(
                        request,
                        f"✅ Profile updated! Coordinates set: {location.latitude:.4f}, {location.longitude:.4f}"
                    )
                else:
                    messages.warning(request, "⚠️ Profile updated, but couldn't find exact coordinates.")
            except (GeocoderTimedOut, GeocoderServiceError):
                messages.warning(request, "⚠️ Profile updated, but geocoding service is temporarily unavailable.")
            except Exception as e:
                messages.warning(request, f"⚠️ Profile updated, but geocoding error: {str(e)}")
        else:
            messages.success(request, "✅ Profile updated successfully.")

        hospital_profile.save()
        return redirect('hospital_profile')

    context = {'hospital': hospital_profile}
    return render(request, 'hospitals/edit_hospital_profile.html', context)


# ============================================
# UTILITY FUNCTIONS
# ============================================
def send_admin_notification(blood_request, donor_count):
    from django.contrib.auth import get_user_model
    from django.core.mail import send_mail
    from django.conf import settings
    User = get_user_model()

    admins = User.objects.filter(is_superuser=True, is_active=True)

    message = f"""
🚨 NEW BLOOD REQUEST - ADMIN ACTION REQUIRED

Hospital: {blood_request.hospital.hospital_name}
Patient: {blood_request.patient_name}
Blood Type: {blood_request.blood_type}
Units Needed: {blood_request.units_needed}
Urgency: {blood_request.urgency_level.upper()}
Condition: {blood_request.condition}

{donor_count} eligible donors found and queued.

LOGIN TO ADMIN PANEL TO MANAGE DONORS:
Go to: /admin/hospitals/bloodrequest/{blood_request.id}/change/
Click "Notify Next Donor" to start sequential notifications.
    """.strip()

    admin_emails = [admin.email for admin in admins if admin.email]
    if admin_emails:
        send_mail(
            subject=f"🚨 URGENT: New Blood Request #{blood_request.id} - {blood_request.blood_type}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=admin_emails,
            fail_silently=True,
        )

    print(f"📧 Admin notification sent for request #{blood_request.id}")
    return True


def send_hospital_acceptance_notification(donor, blood_request, distance):
    from django.core.mail import send_mail
    from django.conf import settings

    hospital = blood_request.hospital

    message = f"""
✅ DONOR ACCEPTED YOUR BLOOD REQUEST!

Request for: {blood_request.patient_name}
Blood Type Required: {blood_request.blood_type}

DONOR DETAILS (Limited Info):
Username: {donor.user.username}
Blood Type: {donor.blood_type}
Distance: {distance:.2f}km

The donor will be contacting you shortly through the platform.

Thank you for using LifeLink Nepal!
    """.strip()

    if hospital.user.email:
        send_mail(
            subject=f"✅ Donor Accepted - Blood Request #{blood_request.id}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[hospital.user.email],
            fail_silently=True,
        )

    print(f"📧 Hospital notified: Donor {donor.user.username} accepted request #{blood_request.id}")
    return True