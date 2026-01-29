# hospitals/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from accounts.decorators import role_required
from .models import BloodRequest, HospitalProfile
from donors.models import DonorProfile, Notification
from algorithms.blood_compatibility import get_compatible_donors, is_compatible
from algorithms.haversine import get_donor_distances, haversine_distance
from algorithms.mcdm import rank_donors_mcdm
from algorithms.priority import run_priority_algorithm


# ============================================
# DASHBOARD
# ============================================
@role_required('hospital')
def hospital_dashboard(request):
    """
    Hospital dashboard showing their blood requests ranked by priority
    """
    hospital_profile = request.user.hospitalprofile
    
    # Get all blood requests for this hospital
    blood_requests = BloodRequest.objects.filter(
        hospital=hospital_profile
    ).order_by('-created_at')
    
    # Rank requests by priority using algorithm
    ranked_requests = run_priority_algorithm(blood_requests)
    
    # Calculate statistics
    pending_count = blood_requests.filter(status='pending').count()
    fulfilled_count = blood_requests.filter(status='fulfilled').count()
    critical_count = len([r for r in ranked_requests if r['priority_level'] == 'critical'])
    
    context = {
        'hospital': hospital_profile,
        'ranked_requests': ranked_requests,
        'total_requests': blood_requests.count(),
        'pending_count': pending_count,
        'fulfilled_count': fulfilled_count,
        'critical_count': critical_count,
    }
    
    return render(request, 'hospitals/hospital_dashboard.html', context)


# ============================================
# BLOOD REQUEST MANAGEMENT
# ============================================
@role_required('hospital')
def create_blood_request(request):
    """
    Create a new blood request and automatically notify matching donors
    Uses all three algorithms: Blood Compatibility, Haversine, and MCDM
    """
    hospital_profile = request.user.hospitalprofile
    
    if request.method == 'POST':
        # Get form data
        patient_name = request.POST.get('patient_name')
        patient_age = request.POST.get('patient_age')
        blood_type = request.POST.get('blood_type')
        units_needed = int(request.POST.get('units_needed', 1))
        urgency_level = request.POST.get('urgency_level')
        condition = request.POST.get('condition', '')
        notes = request.POST.get('notes', '')
        
        # Validate required fields
        if not all([patient_name, blood_type, urgency_level]):
            messages.error(request, "Please fill in all required fields.")
            return render(request, 'hospitals/emergency.html', {
                'hospital': hospital_profile
            })
        
        try:
            # Create the blood request
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
            
            # ALGORITHM 1: Blood Compatibility Filter
            compatible_blood_types = get_compatible_donors(blood_type)
            compatible_donors = DonorProfile.objects.filter(
                blood_type__in=compatible_blood_types,
                is_available=True,
                user__is_active=True
            )
            
            if not compatible_donors.exists():
                messages.warning(
                    request, 
                    f"Blood request created, but no compatible donors are currently available for {blood_type}."
                )
                return redirect('hospital_dashboard')
            
            # ALGORITHM 2: Haversine Distance
            if hospital_profile.latitude and hospital_profile.longitude:
                distances = get_donor_distances(
                    hospital_profile.latitude,
                    hospital_profile.longitude,
                    compatible_donors
                )
                nearby_donor_ids = [donor_id for donor_id, dist in distances.items() if dist <= 50]
                nearby_donors = compatible_donors.filter(id__in=nearby_donor_ids)
            else:
                nearby_donors = compatible_donors
                distances = {}
            
            if not nearby_donors.exists():
                messages.warning(
                    request,
                    f"Blood request created, but no donors found within 50km."
                )
                return redirect('hospital_dashboard')
            
            # ALGORITHM 3: MCDM (TOPSIS) Ranking
            # FIX: Only run MCDM if there are donors to rank
            ranked_donors = []
            if nearby_donors.exists():
                try:
                    ranked_donors = rank_donors_mcdm(
                        nearby_donors,
                        hospital_profile.latitude or 0,
                        hospital_profile.longitude or 0,
                        distances,
                        blood_type
                    )
                except Exception as e:
                    # Fallback: if MCDM fails, just use the nearby donors without ranking
                    print(f"MCDM ranking failed: {e}")
                    ranked_donors = [(donor, 0.5) for donor in nearby_donors[:10]]
            
            # Notify Top Donors
            notification_count = 0
            if ranked_donors:  # Only notify if we have ranked donors
                for donor, mcdm_score in ranked_donors[:10]:
                    Notification.objects.create(
                        donor=donor,
                        blood_request=blood_request,
                        message=f"URGENT: {urgency_level.upper()} blood request for {blood_type}. "
                                f"{units_needed} units needed at {hospital_profile.hospital_name}. "
                                f"You are a {int(mcdm_score * 100)}% match!",
                        is_read=False
                    )
                    send_donor_sms_alert(donor, blood_request, mcdm_score, distances.get(donor.id, 0))
                    notification_count += 1
            
            if notification_count > 0:
                messages.success(
                    request,
                    f"✅ Blood request created! {notification_count} donors notified."
                )
            else:
                messages.success(
                    request,
                    "✅ Blood request created successfully!"
                )
            
            return redirect('view_blood_request', request_id=blood_request.id)
            
        except Exception as e:
            messages.error(request, f"Error creating blood request: {str(e)}")
    
    return render(request, 'hospitals/emergency.html', {
        'hospital': hospital_profile
    })


@role_required('hospital')
def all_blood_requests(request):
    """View all blood requests for this hospital"""
    hospital_profile = request.user.hospitalprofile
    blood_requests = BloodRequest.objects.filter(
        hospital=hospital_profile
    ).order_by('-created_at')
    
    # Rank by priority
    ranked_requests = run_priority_algorithm(blood_requests)
    
    context = {
        'hospital': hospital_profile,
        'ranked_requests': ranked_requests,
    }
    
    return render(request, 'hospitals/all_blood_requests.html', context)


@role_required('hospital')
def view_blood_request(request, request_id):
    """View details of a specific blood request and matching donors"""
    blood_request = get_object_or_404(
        BloodRequest,
        id=request_id,
        hospital=request.user.hospitalprofile
    )
    
    hospital_profile = request.user.hospitalprofile
    
    # Find compatible donors
    compatible_blood_types = get_compatible_donors(blood_request.blood_type)
    compatible_donors = DonorProfile.objects.filter(
        blood_type__in=compatible_blood_types,
        is_available=True
    )
    
    # Calculate distances
    distances = get_donor_distances(
        hospital_profile.latitude or 0,
        hospital_profile.longitude or 0,
        compatible_donors
    )
    
    # Rank donors using MCDM with error handling
    ranked_donors = []
    if compatible_donors.exists():
        try:
            ranked_donors = rank_donors_mcdm(
                compatible_donors,
                hospital_profile.latitude or 0,
                hospital_profile.longitude or 0,
                distances,
                blood_request.blood_type
            )
        except Exception as e:
            print(f"MCDM ranking failed in view_blood_request: {e}")
            # Fallback: show donors without ranking
            ranked_donors = [(donor, 0.5) for donor in compatible_donors[:20]]
    
    # Prepare donor data
    donor_data = []
    for donor, score in ranked_donors[:20]:
        donor_data.append({
            'donor': donor,
            'match_score': round(score * 100, 1),
            'distance': round(distances.get(donor.id, 0), 2),
            'donations': donor.donation_count or 0,
            'can_donate': donor.can_donate,
        })
    
    context = {
        'blood_request': blood_request,
        'donor_data': donor_data,
        'total_donors_found': len(donor_data),
    }
    
    return render(request, 'hospitals/blood_request.html', context)


@role_required('hospital')
def mark_fulfilled(request, request_id):
    """Mark a blood request as fulfilled"""
    blood_request = get_object_or_404(
        BloodRequest,
        id=request_id,
        hospital=request.user.hospitalprofile
    )
    
    blood_request.status = 'fulfilled'
    blood_request.save()
    
    messages.success(request, f"Request for {blood_request.patient_name} marked as fulfilled.")
    return redirect('hospital_dashboard')


@role_required('hospital')
def cancel_request(request, request_id):
    """Cancel a blood request"""
    blood_request = get_object_or_404(
        BloodRequest,
        id=request_id,
        hospital=request.user.hospitalprofile
    )
    
    blood_request.status = 'cancelled'
    blood_request.save()
    
    messages.info(request, "Blood request has been cancelled.")
    return redirect('hospital_dashboard')


# ============================================
# DONOR MANAGEMENT
# ============================================
@role_required('hospital')
def hospital_donors(request):
    """Browse all available donors with filtering"""
    hospital_profile = request.user.hospitalprofile
    
    # Get filter parameters
    blood_type_filter = request.GET.get('blood_type', '')
    max_distance = request.GET.get('max_distance', 50)
    
    # Get all available donors
    donors = DonorProfile.objects.filter(
        is_available=True,
        user__is_active=True
    )
    
    # Filter by blood type if specified
    if blood_type_filter:
        donors = donors.filter(blood_type=blood_type_filter)
    
    # Calculate distances
    if hospital_profile.latitude and hospital_profile.longitude:
        distances = get_donor_distances(
            hospital_profile.latitude,
            hospital_profile.longitude,
            donors
        )
        
        # Filter by distance
        try:
            max_dist = float(max_distance)
            nearby_donor_ids = [donor_id for donor_id, dist in distances.items() if dist <= max_dist]
            donors = donors.filter(id__in=nearby_donor_ids)
        except ValueError:
            pass
    else:
        distances = {}
    
    # Prepare donor data
    donor_list = []
    for donor in donors:
        donor_list.append({
            'donor': donor,
            'distance': round(distances.get(donor.id, 0), 2) if donor.id in distances else None,
        })
    
    # Sort by distance
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
    """View detailed information about a specific donor"""
    donor = get_object_or_404(DonorProfile, id=donor_id)
    hospital_profile = request.user.hospitalprofile
    
    # Calculate distance
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
    """Send notification to a specific donor"""
    donor = get_object_or_404(DonorProfile, id=donor_id)
    hospital_profile = request.user.hospitalprofile
    
    if request.method == 'POST':
        blood_type = request.POST.get('blood_type')
        units_needed = request.POST.get('units_needed', 1)
        urgency = request.POST.get('urgency', 'normal')
        message_text = request.POST.get('message', '')
        
        # Create notification
        Notification.objects.create(
            donor=donor,
            message=f"Blood request from {hospital_profile.hospital_name}: {blood_type}, {units_needed} units. {message_text}",
            is_read=False
        )
        
        messages.success(request, f"Notification sent to {donor.full_name}.")
        return redirect('hospital_donors')
    
    context = {
        'donor': donor,
        'hospital': hospital_profile,
    }
    
    return render(request, 'donors/notify_donor.html', context)


# ============================================
# HOSPITAL PROFILE
# ============================================
@role_required('hospital')
def hospital_profile(request):
    """View hospital profile"""
    hospital_profile = request.user.hospitalprofile
    
    context = {
        'hospital': hospital_profile,
    }
    
    return render(request, 'hospitals/hospital_profile.html', context)


@role_required('hospital')
def edit_hospital_profile(request):
    """Edit hospital profile"""
    hospital_profile = request.user.hospitalprofile
    
    if request.method == 'POST':
        # Update profile fields
        hospital_profile.hospital_name = request.POST.get('hospital_name', hospital_profile.hospital_name)
        hospital_profile.phone = request.POST.get('phone', hospital_profile.phone)
        hospital_profile.address = request.POST.get('address', hospital_profile.address)
        
        # TODO: Geocode address to update latitude/longitude
        
        hospital_profile.save()
        
        messages.success(request, "Profile updated successfully.")
        return redirect('hospital_profile')
    
    context = {
        'hospital': hospital_profile,
    }
    
    return render(request, 'hospitals/hospital_profile.html', context)


# ============================================
# UTILITY FUNCTIONS
# ============================================
def send_donor_sms_alert(donor, blood_request, match_score, distance):
    """
    Send SMS/Call alert to donor
    TODO: Integrate with SMS service (Twilio, SMS Gateway, etc.)
    """
    message = f"""
🔴 URGENT BLOOD NEEDED

Hospital: {blood_request.hospital.hospital_name}
Blood Type: {blood_request.blood_type}
Units: {blood_request.units_needed}
Urgency: {blood_request.urgency_level.upper()}
Distance: {distance:.1f}km

You are a {int(match_score * 100)}% match!

Login to LifeLink Nepal to respond.
    """.strip()
    
    # TODO: Implement actual SMS sending
    print(f"📱 SMS sent to {donor.full_name} ({donor.phone}): {message}")
    
    return True