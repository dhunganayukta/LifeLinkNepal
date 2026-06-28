"""
Haversine Algorithm - Calculate distance between two geographical points
Used to find donors nearest to the hospital requesting blood

UPDATED: Added terrain correction using free elevation APIs (no API key
needed). Pure haversine is "as the crow flies" and badly underestimates
real travel distance in hilly/mountainous terrain like Nepal's hill
districts - two points 5km apart in a straight line can require driving
around a ridge, which can be 2x+ the straight-line distance.

We don't have a road-routing API (OSRM/OpenRouteService), so instead we
fetch elevation for both points and use the elevation difference as a
proxy for how much terrain correction to apply. Bigger elevation gap
relative to distance -> steeper terrain likely between the two points ->
bigger multiplier applied to the raw haversine distance.

If the elevation APIs are unreachable (rate limited, no internet, etc.)
this falls back to flat haversine * a fixed average correction factor,
so donor matching never hard-fails just because a free third-party API
is down - that matters in an emergency blood-donor system.
"""

import math
import time
import logging
import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config for terrain correction
# ---------------------------------------------------------------------------

OPEN_TOPO_DATA_URL = "https://api.opentopodata.org/v1/srtm90m"
OPEN_ELEVATION_URL = "https://api.open-elevation.com/api/v1/lookup"

OPEN_TOPO_DATA_MAX_BATCH = 100      # documented limit per request
ELEVATION_REQUEST_TIMEOUT = 5       # seconds - fail fast, never block matching
ELEVATION_CACHE_TTL = 60 * 60 * 6   # 6 hours - elevation never changes, just bounding memory

# If both elevation APIs are unreachable, fall back to flat haversine with
# this fixed multiplier (rough Nepal-wide average correction).
FALLBACK_FLAT_MULTIPLIER = 1.35

# In-memory cache: {(round(lat, 4), round(lon, 4)): (elevation_m, fetched_at)}
_elevation_cache = {}


# ---------------------------------------------------------------------------
# Original haversine formula - UNCHANGED
# ---------------------------------------------------------------------------

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate straight-line distance between two points.
    Note: This is "as the crow flies" distance, not road distance.
    Actual travel distance may be 20-50% longer depending on roads
    (often much more than that in hilly/mountainous terrain - see
    get_corrected_distance below for a terrain-aware estimate).

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


# ---------------------------------------------------------------------------
# NEW: elevation fetching helpers
# ---------------------------------------------------------------------------

def _cache_key(lat, lon):
    return (round(lat, 4), round(lon, 4))


def _get_cached_elevation(lat, lon):
    key = _cache_key(lat, lon)
    entry = _elevation_cache.get(key)
    if entry is None:
        return None
    elevation, fetched_at = entry
    if time.time() - fetched_at > ELEVATION_CACHE_TTL:
        del _elevation_cache[key]
        return None
    return elevation


def _set_cached_elevation(lat, lon, elevation):
    _elevation_cache[_cache_key(lat, lon)] = (elevation, time.time())


def _fetch_elevations_opentopodata(points):
    """
    points: list of (lat, lon) tuples, max 100 per call.
    Returns: list of elevation floats (meters), same order, or None on failure.
    """
    locations = "|".join(f"{lat},{lon}" for lat, lon in points)
    try:
        resp = requests.get(
            OPEN_TOPO_DATA_URL,
            params={"locations": locations},
            timeout=ELEVATION_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "OK":
            logger.warning("Open Topo Data returned non-OK status: %s", data.get("status"))
            return None
        return [r["elevation"] for r in data["results"]]
    except (requests.RequestException, KeyError, ValueError) as e:
        logger.warning("Open Topo Data request failed: %s", e)
        return None


def _fetch_elevations_openelevation(points):
    """
    Fallback provider. points: list of (lat, lon) tuples.
    Returns: list of elevation floats (meters), same order, or None on failure.
    """
    payload = {"locations": [{"latitude": lat, "longitude": lon} for lat, lon in points]}
    try:
        resp = requests.post(
            OPEN_ELEVATION_URL,
            json=payload,
            timeout=ELEVATION_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return [r["elevation"] for r in data["results"]]
    except (requests.RequestException, KeyError, ValueError) as e:
        logger.warning("Open-Elevation request failed: %s", e)
        return None


def get_elevations(points):
    """
    Get elevations for a list of (lat, lon) points, in meters.
    Uses cache first, then Open Topo Data (batched up to 100/call), then
    Open-Elevation as fallback for any points still missing.

    Returns: dict {(lat, lon): elevation_m}. Points that fail on both
    providers are simply omitted - callers must handle missing keys.
    This makes terrain correction "best effort", not a hard dependency.
    """
    results = {}
    to_fetch = []

    for lat, lon in points:
        cached = _get_cached_elevation(lat, lon)
        if cached is not None:
            results[(lat, lon)] = cached
        else:
            to_fetch.append((lat, lon))

    if not to_fetch:
        return results

    # Try Open Topo Data in batches of up to 100
    still_missing = []
    for i in range(0, len(to_fetch), OPEN_TOPO_DATA_MAX_BATCH):
        batch = to_fetch[i:i + OPEN_TOPO_DATA_MAX_BATCH]
        elevations = _fetch_elevations_opentopodata(batch)
        if elevations is not None and len(elevations) == len(batch):
            for (lat, lon), elev in zip(batch, elevations):
                results[(lat, lon)] = elev
                _set_cached_elevation(lat, lon, elev)
        else:
            still_missing.extend(batch)

    # Fallback to Open-Elevation for anything that failed
    if still_missing:
        elevations = _fetch_elevations_openelevation(still_missing)
        if elevations is not None and len(elevations) == len(still_missing):
            for (lat, lon), elev in zip(still_missing, elevations):
                results[(lat, lon)] = elev
                _set_cached_elevation(lat, lon, elev)
        else:
            logger.warning(
                "Elevation lookup failed for %d points on both providers; "
                "falling back to flat correction for these.",
                len(still_missing),
            )

    return results


def _terrain_multiplier(elevation_diff_m, flat_distance_km):
    """
    Convert an elevation difference into a distance correction multiplier.
    Heuristic, not a physical model:
      - Flat ground (elevation_diff ~ 0) -> multiplier near 1.2x (normal
        road curvature).
      - Bigger elevation_diff relative to flat_distance -> steeper terrain
        likely between the points -> bigger multiplier, capped at 2.8x.

    elevation_diff_m: abs(donor_elevation - hospital_elevation), meters
    flat_distance_km: haversine distance, km
    """
    if flat_distance_km < 0.3:
        # Too close for terrain correction to mean much; avoid noisy spikes.
        return 1.1

    # "Steepness" proxy: meters of elevation change per km of flat distance.
    steepness = elevation_diff_m / flat_distance_km

    # Rough Nepal terrain bands:
    #   <20 m/km   -> flat / Terai-like        -> ~1.2x
    #   20-60 m/km -> rolling hills             -> ~1.4-1.7x
    #   60-120 m/km-> steep hill / mid-mountain -> ~1.8-2.3x
    #   >120 m/km  -> high mountain terrain     -> capped at 2.8x
    if steepness < 20:
        multiplier = 1.2
    elif steepness < 60:
        multiplier = 1.4 + (steepness - 20) / 40 * 0.3   # 1.4 -> 1.7
    elif steepness < 120:
        multiplier = 1.8 + (steepness - 60) / 60 * 0.5   # 1.8 -> 2.3
    else:
        multiplier = min(2.3 + (steepness - 120) / 200 * 0.5, 2.8)

    return multiplier


def get_corrected_distance(hospital_lat, hospital_lon, donor_lat, donor_lon,
                            hospital_elevation=None, donor_elevation=None):
    """
    Estimate terrain-corrected distance (km) between hospital and a single donor.

    hospital_elevation / donor_elevation can be passed in to avoid a redundant
    API call when looping over many donors after a batched get_elevations()
    call (this is what get_donor_distances does below). If omitted, this
    function fetches them itself.

    Returns: (distance_km: float, used_terrain_correction: bool)
    """
    flat_km = haversine_distance(hospital_lat, hospital_lon, donor_lat, donor_lon)

    if hospital_elevation is None or donor_elevation is None:
        elevations = get_elevations([
            (hospital_lat, hospital_lon),
            (donor_lat, donor_lon),
        ])
        hospital_elevation = elevations.get((hospital_lat, hospital_lon))
        donor_elevation = elevations.get((donor_lat, donor_lon))

    if hospital_elevation is None or donor_elevation is None:
        # Both providers failed - fall back to flat multiplier, don't block.
        return flat_km * FALLBACK_FLAT_MULTIPLIER, False

    elevation_diff = abs(donor_elevation - hospital_elevation)
    multiplier = _terrain_multiplier(elevation_diff, flat_km)
    return flat_km * multiplier, True


# ---------------------------------------------------------------------------
# Donor-matching helpers - same names/signatures as before, now terrain-aware
# ---------------------------------------------------------------------------

def find_nearby_donors(hospital_lat, hospital_lon, donors, max_distance=50):
    """
    Find all donors within a specified distance from the hospital.
    Distance is now terrain-corrected (see get_corrected_distance), not
    flat haversine, so the max_distance cutoff reflects realistic travel
    distance rather than straight-line distance.

    Args:
        hospital_lat: Hospital latitude
        hospital_lon: Hospital longitude
        donors: QuerySet or list of donor objects with latitude/longitude
        max_distance: Maximum distance in km (default 50km)

    Returns:
        List of tuples: (donor, distance) sorted by distance ascending
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


def get_donor_distances(hospital_lat, hospital_lon, donors):
    """
    Calculate distance for all donors without filtering.
    Now terrain-corrected by default (was flat haversine before) - this
    is the function algorithms/mcdm.py already calls, so this file can be
    dropped in as-is with no caller changes needed.

    Args:
        hospital_lat: Hospital latitude
        hospital_lon: Hospital longitude
        donors: QuerySet or list of donor objects

    Returns:
        Dictionary mapping donor_id to corrected distance (km)
    """
    eligible_donors = [d for d in donors if d.latitude and d.longitude]
    if not eligible_donors:
        return {}

    # Batch-fetch every elevation needed in as few calls as possible:
    # hospital once, plus every donor location.
    points = [(hospital_lat, hospital_lon)] + [
        (d.latitude, d.longitude) for d in eligible_donors
    ]
    elevations = get_elevations(points)
    hospital_elevation = elevations.get((hospital_lat, hospital_lon))

    distances = {}
    for donor in eligible_donors:
        donor_elevation = elevations.get((donor.latitude, donor.longitude))
        corrected_km, _used_correction = get_corrected_distance(
            hospital_lat, hospital_lon,
            donor.latitude, donor.longitude,
            hospital_elevation=hospital_elevation,
            donor_elevation=donor_elevation,
        )
        distances[donor.id] = corrected_km

    return distances