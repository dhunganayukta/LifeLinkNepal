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


# ============================================
# DASHBOARD
# ============================================
@role_required('hospital')
def hospital_dashboard(request):
    """Hospital dashboard showing blood requests ranked by priority"""
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
    """Create a new blood request and notify top eligible donors"""
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

            # Filter eligible donors using shared eligibility logic
            donors = DonorProfile.objects.filter(is_available=True, user__is_active=True)
            eligible_donors = [d for d in donors if is_donor_eligible(d, blood_request, max_distance=50)]

            if not eligible_donors:
                messages.warning(
                    request,
                    f"Blood request created, but no eligible donors found within 50km."
                )
                return redirect('hospital_dashboard')

            # Rank using MCDM algorithm
            distances = {d.id: d.distance for d in eligible_donors}
            ranked_donors = rank_donors_mcdm(
                eligible_donors,
                hospital_profile.latitude or 0,
                hospital_profile.longitude or 0,
                distances,
                blood_type
            )

            # Notify top 10 donors
            notification_count = 0
            for donor, mcdm_score in ranked_donors[:10]:
                DonorNotification.objects.create(
                    donor=donor,
                    blood_request=blood_request,
                    match_score=mcdm_score,
                    distance=distances.get(donor.id, 0)
                )
                donor.is_read = False
                send_donor_sms_alert(donor, blood_request, mcdm_score, distances.get(donor.id, 0))
                notification_count += 1

            messages.success(
                request,
                f"✅ Blood request created! {notification_count} donors notified."
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
    blood_requests = BloodRequest.objects.filter(
        hospital=hospital_profile
    ).order_by('-created_at')

    ranked_requests = run_priority_algorithm(blood_requests)
    context = {
        'hospital': hospital_profile,
        'ranked_requests': ranked_requests,
    }
    return render(request, 'hospitals/all_blood_requests.html', context)


# ============================================
# VIEW SINGLE BLOOD REQUEST & DONORS
# ============================================
@role_required('hospital')
def view_blood_request(request, request_id):
    blood_request = get_object_or_404(BloodRequest, id=request_id, hospital=request.user.hospitalprofile)
    hospital_profile = request.user.hospitalprofile

    donors = DonorProfile.objects.filter(is_available=True, user__is_active=True)
    eligible_donors = [d for d in donors if is_donor_eligible(d, blood_request, max_distance=50)]
    distances = {d.id: d.distance for d in eligible_donors}

    ranked_donors = []
    if eligible_donors:
        try:
            ranked_donors = rank_donors_mcdm(
                eligible_donors,
                hospital_profile.latitude or 0,
                hospital_profile.longitude or 0,
                distances,
                blood_request.blood_type
            )
        except Exception as e:
            print(f"MCDM ranking failed in view_blood_request: {e}")
            ranked_donors = [(d, 0.5) for d in eligible_donors[:20]]

    donor_data = []
    for donor, score in ranked_donors[:20]:
        # Safely handle None distance and score values
        raw_distance = distances.get(donor.id)
        distance_display = round(raw_distance, 2) if raw_distance is not None else None
        match_display = round(score * 100, 1) if score is not None else 0.0

        donor_data.append({
            'donor': donor,
            'match_score': match_display,
            'distance': distance_display,
            'donations': donor.donation_count or 0,
            'can_donate': donor.can_donate,
        })

    context = {
        'blood_request': blood_request,
        'donor_data': donor_data,
        'total_donors_found': len(donor_data),
    }
    return render(request, 'hospitals/blood_request.html', context)


# ============================================
# MARK FULFILLED / CANCEL
# ============================================
@role_required('hospital')
def mark_fulfilled(request, request_id):
    blood_request = get_object_or_404(BloodRequest, id=request_id, hospital=request.user.hospitalprofile)
    blood_request.status = 'fulfilled'
    blood_request.save()
    messages.success(request, f"Request for {blood_request.patient_name} marked as fulfilled.")
    return redirect('hospital_dashboard')


@role_required('hospital')
def cancel_request(request, request_id):
    blood_request = get_object_or_404(BloodRequest, id=request_id, hospital=request.user.hospitalprofile)
    blood_request.status = 'cancelled'
    blood_request.save()
    messages.info(request, "Blood request has been cancelled.")
    return redirect('hospital_dashboard')


# ============================================
# DONOR MANAGEMENT
# ============================================
@role_required('hospital')
def hospital_donors(request):
    hospital_profile = request.user.hospitalprofile
    blood_type_filter = request.GET.get('blood_type', '')
    max_distance = request.GET.get('max_distance', 50)

    donors = DonorProfile.objects.filter(is_available=True, user__is_active=True)
    if blood_type_filter:
        donors = donors.filter(blood_type=blood_type_filter)

    distances = {}
    if hospital_profile.latitude and hospital_profile.longitude:
        distances = {d.id: haversine_distance(hospital_profile.latitude, hospital_profile.longitude, d.latitude, d.longitude)
                     for d in donors if d.latitude and d.longitude}
        try:
            max_dist = float(max_distance)
            nearby_ids = [d_id for d_id, dist in distances.items() if dist <= max_dist]
            donors = donors.filter(id__in=nearby_ids)
        except ValueError:
            pass

    donor_list = []
    for donor in donors:
        donor_list.append({
            'donor': donor,
            'distance': round(distances.get(donor.id, 0), 2) if donor.id in distances else None,
        })

    donor_list.sort(key=lambda x: x['distance'] if x['distance'] is not None else 999)

    context = {
        'hospital': hospital_profile,
        'donor_list': donor_list,
        'blood_type_filter': blood_type_filter,
        'max_distance': max_distance,
    }
    return render(request, 'hospitals/hospital_donors.html', context)


@role_required('hospital')
def view_donor_detail(request, donor_id):
    donor = get_object_or_404(DonorProfile, id=donor_id)
    hospital_profile = request.user.hospitalprofile

    distance = None
    if hospital_profile.latitude and donor.latitude:
        distance = haversine_distance(
            hospital_profile.latitude,
            hospital_profile.longitude,
            donor.latitude,
            donor.longitude
        )

    context = {
        'donor': donor,
        'hospital': hospital_profile,
        'distance': round(distance, 2) if distance else None,
    }
    return render(request, 'donors/view_donor_detail.html', context)


@role_required('hospital')
def notify_donor(request, donor_id):
    donor = get_object_or_404(DonorProfile, id=donor_id)
    hospital_profile = request.user.hospitalprofile

    if request.method == 'POST':
        blood_type = request.POST.get('blood_type')
        units_needed = request.POST.get('units_needed', 1)
        urgency = request.POST.get('urgency', 'normal')
        message_text = request.POST.get('message', '')
        # Send email / log the ad-hoc notification (no DB model for generic messages)
        if donor.user.email:
            from django.core.mail import send_mail
            from django.conf import settings
            send_mail(
                subject=f"Message from {hospital_profile.hospital_name}",
                message=f"Blood request: {blood_type}, {units_needed} units. Message: {message_text}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[donor.user.email],
                fail_silently=True,
            )

        messages.success(request, f"Notification sent to {donor.full_name} (email/SMS simulated).")
        return redirect('hospital_donors')

    context = {'donor': donor, 'hospital': hospital_profile}
    return render(request, 'donors/notify_donor.html', context)


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
        hospital_profile.hospital_name = request.POST.get('hospital_name', hospital_profile.hospital_name)
        hospital_profile.phone = request.POST.get('phone', hospital_profile.phone)
        hospital_profile.address = request.POST.get('address', hospital_profile.address)
        # TODO: Geocode address
        hospital_profile.save()
        messages.success(request, "Profile updated successfully.")
        return redirect('hospital_profile')

    context = {'hospital': hospital_profile}
    return render(request, 'hospitals/hospital_profile.html', context)


# ============================================
# UTILITY
# ============================================
def send_donor_sms_alert(donor, blood_request, match_score, distance):
    """Send SMS alert to donor (placeholder)"""
    # Guard against None distance/match_score
    distance_val = 0.0 if distance is None else float(distance)
    match_val = 0.0 if match_score is None else float(match_score)

    message = f"""
🔴 URGENT BLOOD NEEDED

Hospital: {blood_request.hospital.hospital_name}
Blood Type: {blood_request.blood_type}
Units: {getattr(blood_request, 'units_needed', '')}
Urgency: {blood_request.urgency_level.upper()}
Distance: {distance_val:.1f}km

You are a {int(match_val * 100)}% match!

Login to LifeLink Nepal to respond.
    """.strip()
    print(f"📱 SMS to {donor.full_name} ({donor.phone}): {message}")
    return True
