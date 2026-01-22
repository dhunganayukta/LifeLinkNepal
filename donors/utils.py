# donors/utils.py
from donors.models import DonorProfile, Notification
from hospitals.models import EmergencyRequest
from algorithms.haversine import haversine_distance
from algorithms.mcdm import rank_donors_mcdm
from algorithms.blood_compatibility import is_compatible

def match_donors(emergency_request):
    """
    Match donors for an emergency request based on:
    - Blood compatibility
    - Distance (Haversine)
    - Rank using MCDM
    """
    # Filter active donors
    donors = DonorProfile.objects.filter(is_active=True)

    # Filter compatible blood groups
    compatible_donors = [
        d for d in donors if is_compatible(d.blood_group, emergency_request.blood_group)
    ]

    # Calculate distance from hospital
    for donor in compatible_donors:
        donor.distance = haversine_distance(
            emergency_request.hospital.latitude,
            emergency_request.hospital.longitude,
            donor.latitude,
            donor.longitude
        )

    # Rank using MCDM
    ranked_donors = rank_donors_mcdm(compatible_donors)

    return ranked_donors


def send_notification(donors, emergency_request):
    """
    Notify matched donors about a new emergency request.
    """
    for donor in donors:
        Notification.objects.create(
            donor=donor,
            message=f"New emergency request for {emergency_request.blood_group} blood at {emergency_request.hospital.name}"
        )
