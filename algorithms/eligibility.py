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
    if donor.latitude and donor.longitude and getattr(blood_request.hospital, 'latitude', None) and getattr(blood_request.hospital, 'longitude', None):
        distance = haversine_distance(
            donor.latitude,
            donor.longitude,
            blood_request.hospital.latitude,
            blood_request.hospital.longitude
        )
        if distance > max_distance:
            return False
        donor.distance = round(distance, 2)  # Attach distance for display/ranking
    else:
        donor.distance = None

    return True
