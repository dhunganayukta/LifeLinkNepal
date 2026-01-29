# algorithms/mcdm.py - FIXED VERSION
import numpy as np
from datetime import datetime, timedelta

def rank_donors_mcdm(donors, hospital_lat, hospital_lon, distances, required_blood_type):
    """
    Rank donors using MCDM (TOPSIS) algorithm
    
    Criteria:
    1. Distance (minimize)
    2. Blood compatibility (maximize)
    3. Donation count (maximize)
    4. Days since last donation (maximize)
    """
    
    # FIX: Handle empty donor list and accept querysets or lists
    donor_list = list(donors) if donors is not None else []
    if len(donor_list) == 0:
        return []
    
    # FIX: Handle single donor
    if len(donor_list) == 1:
        return [(donor_list[0], 1.0)]
    
    # Prepare criteria matrix
    criteria_matrix = []
    
    for donor in donor_list:
        # Distance (km) - lower is better
        distance = distances.get(donor.id, 50)  # default 50km if not calculated
        
        # Blood compatibility score (0-10)
        compatibility = get_blood_compatibility_score(donor.blood_type, required_blood_type)
        
        # Donation count (higher is better)
        donation_count = donor.donation_count or 0
        
        # Days since last donation (higher is better, max 90)
        if donor.last_donation_date:
            days_since = (datetime.now().date() - donor.last_donation_date).days
            days_since = min(days_since, 90)  # Cap at 90
        else:
            days_since = 90  # Never donated = best recency
        
        criteria_matrix.append([
            distance,
            compatibility,
            donation_count,
            days_since
        ])
    
    # Convert to numpy array
    matrix = np.array(criteria_matrix, dtype=float)
    
    # FIX: Check if matrix has valid values
    if matrix.size == 0:
        return [(donor, 0.5) for donor in donor_list]
    
    # Normalize the matrix
    normalized = normalize_matrix(matrix)
    
    # Weights for each criterion (must sum to 1)
    weights = np.array([0.3, 0.3, 0.2, 0.2])  # distance, compatibility, donations, recency
    
    # Weighted normalized matrix
    weighted = normalized * weights
    
    # Ideal and negative-ideal solutions
    # FIX: Use axis parameter and handle empty arrays
    try:
        # For distance (minimize): ideal is min, negative-ideal is max
        # For others (maximize): ideal is max, negative-ideal is min
        ideal = np.array([
            weighted[:, 0].min() if weighted.shape[0] > 0 else 0,  # distance (minimize)
            weighted[:, 1].max() if weighted.shape[0] > 0 else 1,  # compatibility (maximize)
            weighted[:, 2].max() if weighted.shape[0] > 0 else 1,  # donations (maximize)
            weighted[:, 3].max() if weighted.shape[0] > 0 else 1   # recency (maximize)
        ])
        
        negative_ideal = np.array([
            weighted[:, 0].max() if weighted.shape[0] > 0 else 1,  # distance (maximize)
            weighted[:, 1].min() if weighted.shape[0] > 0 else 0,  # compatibility (minimize)
            weighted[:, 2].min() if weighted.shape[0] > 0 else 0,  # donations (minimize)
            weighted[:, 3].min() if weighted.shape[0] > 0 else 0   # recency (minimize)
        ])
    except Exception as e:
        print(f"Error calculating ideal solutions: {e}")
        return [(donor, 0.5) for donor in donor_list]
    
    # Calculate separation measures
    scores = []
    for i in range(len(weighted)):
        # Distance to ideal solution
        d_positive = np.sqrt(np.sum((weighted[i] - ideal) ** 2))
        
        # Distance to negative-ideal solution
        d_negative = np.sqrt(np.sum((weighted[i] - negative_ideal) ** 2))
        
        # TOPSIS score (0 to 1, higher is better)
        # FIX: Handle division by zero
        if d_positive + d_negative > 0:
            score = d_negative / (d_positive + d_negative)
        else:
            score = 0.5
        
        scores.append(score)
    
    # Combine donors with their scores and sort
    ranked = list(zip(donor_list, scores))
    ranked.sort(key=lambda x: x[1], reverse=True)
    
    return ranked


def normalize_matrix(matrix):
    """
    Normalize the decision matrix using vector normalization
    """
    # FIX: Handle empty matrix
    if matrix.size == 0:
        return matrix
    
    normalized = np.zeros_like(matrix, dtype=float)
    
    for j in range(matrix.shape[1]):
        column = matrix[:, j]
        # FIX: Handle zero sum
        column_sum = np.sqrt(np.sum(column ** 2))
        if column_sum > 0:
            normalized[:, j] = column / column_sum
        else:
            normalized[:, j] = 0
    
    return normalized


def get_blood_compatibility_score(donor_type, required_type):
    """
    Score blood compatibility (0-10)
    10 = exact match, 8 = compatible, 0 = incompatible
    """
    compatibility_matrix = {
        'O-': {'O-': 10, 'O+': 8, 'A-': 8, 'A+': 8, 'B-': 8, 'B+': 8, 'AB-': 8, 'AB+': 8},
        'O+': {'O+': 10, 'A+': 8, 'B+': 8, 'AB+': 8},
        'A-': {'A-': 10, 'A+': 8, 'AB-': 8, 'AB+': 8},
        'A+': {'A+': 10, 'AB+': 8},
        'B-': {'B-': 10, 'B+': 8, 'AB-': 8, 'AB+': 8},
        'B+': {'B+': 10, 'AB+': 8},
        'AB-': {'AB-': 10, 'AB+': 8},
        'AB+': {'AB+': 10},
    }
    
    return compatibility_matrix.get(donor_type, {}).get(required_type, 0)