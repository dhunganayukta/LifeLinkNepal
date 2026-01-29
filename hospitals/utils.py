import logging
from datetime import date
from django.core.mail import send_mail
from django.conf import settings
from algorithms.eligibility import is_donor_eligible
from donors.models import DonorProfile, DonorNotification, DonorResponse
from algorithms.blood_compatibility import is_compatible
from algorithms.haversine import haversine_distance

# Constants
MAX_DISTANCE_KM = 25
DONATION_COOLDOWN_DAYS = 90

# Logger setup
logger = logging.getLogger(__name__)


def is_donor_eligible_for_hospital_request(donor, blood_request, max_distance=MAX_DISTANCE_KM):
    """
    Check if donor is eligible for a hospital blood request.

    Criteria:
    - Donor is available
    - Donor blood type compatible
    - Donor hasn't donated in last 90 days
    - Donor hasn't declined this request
    - Donor is within max_distance km of hospital
    """
    if not donor.is_available:
        return False

    if donor.last_donation_date:
        days_since_last = (date.today() - donor.last_donation_date).days
        if days_since_last < DONATION_COOLDOWN_DAYS:
            return False

    if not is_compatible(donor.blood_type, blood_request.blood_type):
        return False

    if DonorResponse.objects.filter(donor=donor, blood_request=blood_request, status='declined').exists():
        return False

    # Distance calculation
    if donor.latitude and donor.longitude and blood_request.hospital.latitude and blood_request.hospital.longitude:
        distance = haversine_distance(
            donor.latitude,
            donor.longitude,
            blood_request.hospital.latitude,
            blood_request.hospital.longitude
        )
        if distance > max_distance:
            return False
        donor.distance = round(distance, 2)
    else:
        donor.distance = None

    return True


def notify_next_eligible_donor(blood_request):
    """
    Find and notify the next eligible donor for a blood request.
    """
    donors = DonorProfile.objects.filter(is_available=True)
    eligible_donors = [d for d in donors if is_donor_eligible(d, blood_request)]

    # Sort by last donation (donor who hasn't donated recently first)
    eligible_donors.sort(key=lambda d: d.last_donation_date or date(2000, 1, 1))

    if eligible_donors:
        next_donor = eligible_donors[0]
        send_blood_request_notification(next_donor, blood_request)
        logger.info(f"Next eligible donor {next_donor.user.username} notified for request {blood_request.id}")
    else:
        logger.info(f"No eligible donors found for request {blood_request.id}")


def send_blood_request_notification(donor, blood_request):
    """
    Notify a donor about a hospital blood request.
    Saves DB notification and sends email if available.
    """
    message = f"""
Blood Request Alert!

Request ID: {blood_request.id}
Hospital: {blood_request.hospital.hospital_name}
Location: {blood_request.hospital.address}
Blood Type Needed: {blood_request.blood_type}
Urgency Level: {blood_request.urgency_level}

Please log in to your donor dashboard to ACCEPT or DECLINE.
"""
    # Save notification in the DonorNotification model (no message field here)
    DonorNotification.objects.create(
        donor=donor,
        blood_request=blood_request,
        match_score=None,
        distance=None
    )

    # Send email
    if donor.user.email:
        send_mail(
            subject=f"Blood Request: {blood_request.blood_type} Needed",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[donor.user.email],
            fail_silently=True,
        )

    # TODO: Integrate SMS (Twilio/Nexmo)
    logger.info(f"Notification sent to {donor.user.username} ({donor.phone})")


def notify_hospital_of_acceptance(blood_request, donor):
    """
    Notify hospital that a donor accepted a blood request.
    Only show minimal donor info for privacy.
    """
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

    # TODO: Save hospital notification in DB if model exists

    # Send email to hospital
    if hospital.email:
        send_mail(
            subject=f"Donor Accepted: Blood Request {blood_request.id}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[hospital.email],
            fail_silently=True,
        )

    logger.info(f"Hospital {hospital.hospital_name} notified: donor {donor.user.username} accepted request")
