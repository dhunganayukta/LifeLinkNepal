import logging
from datetime import date
from donors.models import DonorProfile, DonorNotification, DonorResponse
from hospitals.models import BloodRequest as EmergencyRequest
from algorithms.eligibility import is_donor_eligible
from algorithms.haversine import haversine_distance
from algorithms.mcdm import rank_donors_mcdm
from algorithms.blood_compatibility import is_compatible

# Constants
MAX_DISTANCE_KM = 25
DONATION_COOLDOWN_DAYS = 90

# Logger setup
logger = logging.getLogger(__name__)


def is_donor_eligible_for_request(donor, emergency_request, max_distance=MAX_DISTANCE_KM):
    """
    Check if a donor is eligible for a specific emergency request.
    Criteria:
    - Donor is available
    - Donor blood type compatible
    - Donor hasn't donated in the last 90 days
    - Donor hasn't previously declined this request
    - Donor is within max_distance km of hospital
    """
    if not donor.is_available:
        return False

    if donor.last_donation_date:
        days_since_last = (date.today() - donor.last_donation_date).days
        if days_since_last < DONATION_COOLDOWN_DAYS:
            return False

    if not is_compatible(donor.blood_type, emergency_request.blood_type):
        return False

    if DonorResponse.objects.filter(donor=donor, blood_request=emergency_request, status='declined').exists():
        return False

    # Distance check
    if donor.latitude and donor.longitude and emergency_request.hospital.latitude and emergency_request.hospital.longitude:
        distance = haversine_distance(
            emergency_request.hospital.latitude,
            emergency_request.hospital.longitude,
            donor.latitude,
            donor.longitude
        )
        if distance > max_distance:
            return False
        donor.distance = round(distance, 2)  # attach distance for ranking/display
    else:
        donor.distance = None

    return True


def match_donors(emergency_request):
    """
    Match and rank eligible donors for an emergency request.
    Steps:
    1. Filter available donors
    2. Apply eligibility check
    3. Rank using MCDM algorithm
    """
    donors = DonorProfile.objects.filter(is_available=True)

    eligible_donors = [d for d in donors if is_donor_eligible(d, emergency_request)]

    ranked_donors = rank_donors_mcdm(eligible_donors)

    logger.info(f"{len(ranked_donors)} donors matched for emergency request {emergency_request.id}")
    return ranked_donors


def send_notification(donors, emergency_request):
    """
    Notify matched donors about a new emergency request.
    Saves DB notification and logs info.
    """
    for donor in donors:
        message = f"""
Blood Request Alert!

Request ID: {emergency_request.id}
Hospital: {emergency_request.hospital.hospital_name}
Location: {emergency_request.hospital.address}
Blood Type Needed: {emergency_request.blood_type}
Urgency Level: {emergency_request.urgency_level}

Please log in to your donor dashboard to ACCEPT or DECLINE.
"""
        DonorNotification.objects.create(
            donor=donor,
            blood_request=emergency_request,
            match_score=None,
            distance=None
        )

        # TODO: Integrate Email/SMS here
        logger.info(f"Notification sent to {donor.user.username} ({donor.phone})")
