
import numpy as np
from datetime import datetime
from algorithms.blood_compatibility import is_compatible
def rank_donors_mcdm(donors, hospital_lat, hospital_lon, distances, required_blood_type):
    """
    Rank donors using MCDM (TOPSIS) algorithm.

    Blood compatibility is now a HARD FILTER applied before ranking,
    not a soft weighted criterion. This prevents an incompatible donor
    (e.g. AB- for an A+ request) from ever outranking a compatible donor
    just because they score better on distance/donations/recency.

    Criteria used in TOPSIS (only for donors who already passed the
    compatibility filter):
    1. Distance (minimize)
    2. Donation count (maximize)
    3. Days since last donation (maximize)
    """
    donor_list = list(donors) if donors is not None else []
    if len(donor_list) == 0:
        return []
    donor_list = [
        d for d in donor_list
        if is_compatible(d.blood_type, required_blood_type)
    ]

    if len(donor_list) == 0:
        return []
    if len(donor_list) == 1:
        return [(donor_list[0], 1.0)]
    criteria_matrix = []
    for donor in donor_list:
        distance = distances.get(donor.id, 50) 
        donation_count = donor.donation_count or 0
        if donor.last_donation_date:
            days_since = (datetime.now().date() - donor.last_donation_date).days
            days_since = min(days_since, 90)
        else:
            days_since = 90  

        criteria_matrix.append([
            distance,
            donation_count,
            days_since
        ])

    matrix = np.array(criteria_matrix, dtype=float)

    if matrix.size == 0:
        return [(donor, 0.5) for donor in donor_list]
    normalized = normalize_matrix(matrix)
    weights = np.array([0.45, 0.30, 0.25])  # distance, donations, recency

    weighted = normalized * weights

    try:
        ideal = np.array([
            weighted[:, 0].min(),  # distance (minimize)
            weighted[:, 1].max(),  # donations (maximize)
            weighted[:, 2].max()   # recency (maximize)
        ])
        negative_ideal = np.array([
            weighted[:, 0].max(),  # distance (worst = farthest)
            weighted[:, 1].min(),  # donations (worst = fewest)
            weighted[:, 2].min()   # recency (worst = most recent donation)
        ])
    except Exception as e:
        print(f"Error calculating ideal solutions: {e}")
        return [(donor, 0.5) for donor in donor_list]
    scores = []
    for i in range(len(weighted)):
        d_positive = np.sqrt(np.sum((weighted[i] - ideal) ** 2))
        d_negative = np.sqrt(np.sum((weighted[i] - negative_ideal) ** 2))

        if d_positive + d_negative > 0:
            score = d_negative / (d_positive + d_negative)
        else:
            score = 0.5
        scores.append(score)
    ranked = list(zip(donor_list, scores))
    ranked.sort(key=lambda x: x[1], reverse=True)

    return ranked
def normalize_matrix(matrix):
    """
    Normalize the decision matrix using vector normalization.
    """
    if matrix.size == 0:
        return matrix

    normalized = np.zeros_like(matrix, dtype=float)

    for j in range(matrix.shape[1]):
        column = matrix[:, j]
        column_sum = np.sqrt(np.sum(column ** 2))
        if column_sum > 0:
            normalized[:, j] = column / column_sum
        else:
            normalized[:, j] = 0

    return normalized