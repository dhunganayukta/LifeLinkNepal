"""
Haversine Algorithm - Calculate distance between two geographical points
Used to find donors nearest to the hospital requesting blood
"""

import math

def haversine_distance(lat1, lon1, lat2, lon2):
    """
   Calculate straight-line distance between two points.
    Note: This is "as the crow flies" distance, not road distance.
    Actual travel distance may be 20-50% longer depending on roads.

    
    Args:
        lat1, lon1: Latitude and longitude of point 1 (hospital)
        lat2, lon2: Latitude and longitude of point 2 (donor)
    
    Returns:
        Distance in kilometers
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of earth in kilometers
    r = 6371
    
    return c * r


def find_nearby_donors(hospital_lat, hospital_lon, donors, max_distance=50):
    """
    Find all donors within a specified distance from the hospital
    
    Args:
        hospital_lat: Hospital latitude
        hospital_lon: Hospital longitude
        donors: QuerySet or list of donor objects with latitude/longitude
        max_distance: Maximum distance in km (default 50km)
    
    Returns:
        List of tuples: (donor, distance) sorted by distance
    """
    nearby_donors = []
    
    for donor in donors:
        if donor.latitude and donor.longitude:
            distance = haversine_distance(
                hospital_lat, 
                hospital_lon, 
                donor.latitude, 
                donor.longitude
            )
            
            if distance <= max_distance:
                nearby_donors.append((donor, distance))
    
    # Sort by distance (closest first)
    nearby_donors.sort(key=lambda x: x[1])
    
    return nearby_donors


def get_donor_distances(hospital_lat, hospital_lon, donors):
    """
    Calculate distance for all donors without filtering
    
    Args:
        hospital_lat: Hospital latitude
        hospital_lon: Hospital longitude
        donors: QuerySet or list of donor objects
    
    Returns:
        Dictionary mapping donor_id to distance
    """
    distances = {}
    
    for donor in donors:
        if donor.latitude and donor.longitude:
            distance = haversine_distance(
                hospital_lat,
                hospital_lon,
                donor.latitude,
                donor.longitude
            )
            distances[donor.id] = distance
    
    return distances