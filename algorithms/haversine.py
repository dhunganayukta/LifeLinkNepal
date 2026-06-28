"""
Haversine Algorithm - Calculate distance between two geographical points
Used to find donors nearest to the hospital requesting blood

DESIGN NOTE (read before changing this file):
We deliberately do NOT do terrain/elevation correction here, even though
Nepal's hill and mountain districts mean straight-line distance often
understates real travel distance. An earlier version of this file tried
to estimate travel distance using elevation-difference heuristics from
free third-party elevation APIs (Open Topo Data / Open-Elevation). That
was reverted because:

  1. It put two unreliable third-party network calls in the critical path
     of emergency donor matching - exactly the step that must never be
     slow or flaky.
  2. The "correction" was a heuristic guess from elevation gap, not real
     road distance - it could just as easily rank a donor with a great
     paved road across a valley as "far" while ranking a donor blocked by
     a river with no nearby bridge as "close". For a system whose output
     decides who gets called for an emergency, a confidently-wrong number
     is worse than an honestly-approximate one.

Instead: this module computes plain haversine ("as the crow flies")
distance, fast and dependency-free, used ONLY for ranking/filtering
candidate donors. Anything resembling "is this donor actually reachable"
is explicitly left to the human coordinator, who knows local roads,
landslides, closed bridges, etc. better than any heuristic will.

Every distance value returned by this module should be displayed to staff
with the word "approx." / "straight-line" attached - see
format_distance_label() below - so nobody mistakes it for travel distance
or ETA. If/when real road-routing (e.g. a self-hosted OSRM instance) is
available, that should replace this for any user-facing "distance" or ETA,
not extend this heuristic further.
"""

import math
DISTANCE_LABEL_SUFFIX = "km (approx., straight-line)"
def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate straight-line ("as the crow flies") distance between two points.

    This is intentionally NOT road distance. In hilly/mountainous terrain
    (much of Nepal outside the Terai), actual travel distance can be
    significantly longer than this - sometimes 2x+ - because roads have to
    go around ridges, follow valleys, or detour to river crossings. This
    function does not attempt to correct for that; see module docstring for
    why. Use this for fast ranking/filtering only, and always label the
    result as approximate when shown to a person.

    Args:
        lat1, lon1: Latitude and longitude of point 1 (hospital)
        lat2, lon2: Latitude and longitude of point 2 (donor)

    Returns:
        Distance in kilometers (float)
    """
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    r = 6371  # Earth radius, km
    return c * r
def format_distance_label(distance_km, decimals=1):
    """
    Format a haversine distance for display to hospital staff/coordinators,
    always making clear it's a straight-line approximation and not a travel
    distance or ETA. Use this (or equivalent wording) anywhere a distance
    from this module reaches a UI, notification, or report.
    Args:
        distance_km: distance in kilometers, as returned by this module
        decimals: number of decimal places to show

    Returns:
        e.g. "6.4 km (approx., straight-line)"
    """
    return f"{distance_km:.{decimals}f} {DISTANCE_LABEL_SUFFIX}"
def get_donor_distances(hospital_lat, hospital_lon, donors):
    """
    Calculate straight-line distance for all donors without filtering.
    No network calls, no terrain correction - fast and always available,
    which matters for an emergency-matching code path.

    Args:
        hospital_lat: Hospital latitude
        hospital_lon: Hospital longitude
        donors: QuerySet or list of donor objects with latitude/longitude

    Returns:
        Dictionary mapping donor_id to straight-line distance (km).
        Treat these as approximate; see module docstring.
    """
    eligible_donors = [d for d in donors if d.latitude and d.longitude]
    if not eligible_donors:
        return {}

    distances = {}
    for donor in eligible_donors:
        distances[donor.id] = haversine_distance(
            hospital_lat, hospital_lon, donor.latitude, donor.longitude
        )
    return distances
def find_nearby_donors(hospital_lat, hospital_lon, donors, max_distance=50):
    """
    Find all donors within a specified straight-line distance from the
    hospital. Because this is straight-line, not road, distance, treat
    max_distance as a generous first-pass filter rather than a hard
    cutoff on reachability - a donor just outside max_distance by air may
    still be on a direct road, and a donor just inside it may be much
    further by the only available road. The human coordinator should make
    the final call on which nearby donors to actually contact, using local
    knowledge of roads/conditions.
    Args:
        hospital_lat: Hospital latitude
        hospital_lon: Hospital longitude
        donors: QuerySet or list of donor objects with latitude/longitude
        max_distance: Maximum straight-line distance in km (default 50km)

    Returns:
        List of tuples: (donor, distance_km) sorted by distance ascending.
        distance_km is straight-line - format with format_distance_label()
        before showing to a person.
    """
    eligible_donors = [d for d in donors if d.latitude and d.longitude]
    distances = get_donor_distances(hospital_lat, hospital_lon, eligible_donors)

    nearby_donors = [
        (donor, distances[donor.id])
        for donor in eligible_donors
        if donor.id in distances and distances[donor.id] <= max_distance
    ]

    nearby_donors.sort(key=lambda x: x[1])
    return nearby_donors