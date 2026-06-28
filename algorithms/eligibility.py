import logging
from datetime import date
from donors.models import DonorProfile, DonorResponse
from algorithms.haversine import haversine_distance
from algorithms.blood_compatibility import is_compatible

# Constants
MAX_DISTANCE_KM = 25
DONATION_COOLDOWN_DAYS = 90

# Logger
logger = logging.getLogger(__name__)


def is_donor_eligible(donor: DonorProfile, blood_request, max_distance: int = MAX_DISTANCE_KM) -> bool:
    """
    Check if a donor is eligible for a given blood request.

    Criteria:
    - Donor is available
    - Donor blood type compatible with request
    - Donor hasn't donated in the last 90 days
    - Donor hasn't previously declined this request
    - Donor is within max_distance km of hospital
    - Donor and hospital both have known coordinates (FIX: previously
      missing coordinates were treated as "eligible by default" — now
      they correctly fail the check instead, since distance can't be
      verified)

    Args:
        donor (DonorProfile): Donor object
        blood_request: EmergencyRequest or BloodRequest object
        max_distance (int): Maximum distance in km

    Returns:
        bool: True if eligible, False otherwise
    """
    if not donor.is_available:
        return False

    # Donation cooldown
    if donor.last_donation_date:
        days_since_last = (date.today() - donor.last_donation_date).days
        if days_since_last < DONATION_COOLDOWN_DAYS:
            return False

    # Blood compatibility
    if not is_compatible(donor.blood_type, blood_request.blood_type):
        return False

    # Check if donor previously declined
    if DonorResponse.objects.filter(donor=donor, blood_request=blood_request, status='declined').exists():
        return False

    # Distance check
    hospital_lat = getattr(blood_request.hospital, 'latitude', None)
    hospital_lon = getattr(blood_request.hospital, 'longitude', None)

    if (
        donor.latitude is not None and donor.longitude is not None
        and hospital_lat is not None and hospital_lon is not None
    ):
        distance = haversine_distance(
            donor.latitude,
            donor.longitude,
            hospital_lat,
            hospital_lon
        )
        if distance > max_distance:
            return False
        donor.distance = round(distance, 2)  # Attach distance for display/ranking
    else:
        # FIX: previously this set donor.distance = None and returned True,
        # i.e. a donor with missing GPS data passed eligibility by default.
        # That's the wrong failure mode for an emergency dispatch system —
        # we can't confirm they're within range, so we exclude them rather
        # than silently assume they're close enough.
        logger.warning(
            f"Donor {donor.id} or hospital {getattr(blood_request.hospital, 'id', '?')} "
            f"missing coordinates - excluding donor from distance-based eligibility"
        )
        donor.distance = None
        return False

    return True