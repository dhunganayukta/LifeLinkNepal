# algorithms/priority.py
from datetime import datetime, timedelta
from django.utils import timezone  # Import timezone utility

def run_priority_algorithm(blood_requests):
    """
    Priority Algorithm: Ranks blood requests by urgency, time waiting, units needed, and blood rarity
    Returns a list of dicts with request data and priority info
    """
    # Accept either a queryset or a plain list; normalize to list
    requests_list = list(blood_requests) if blood_requests is not None else []
    if len(requests_list) == 0:
        return []
    
    ranked_list = []
    
    for request in requests_list:
        # Calculate individual scores
        urgency_score = calculate_urgency_score(request.urgency_level)
        time_score = calculate_time_score(request.created_at)
        units_score = calculate_units_score(request.units_needed)
        blood_rarity_score = calculate_blood_rarity_score(request.blood_type)
        
        # Weighted priority score (0-100)
        priority_score = (
            urgency_score * 0.40 +    # 40% weight on urgency
            time_score * 0.30 +        # 30% weight on waiting time
            units_score * 0.20 +       # 20% weight on units needed
            blood_rarity_score * 0.10  # 10% weight on blood rarity
        )
        
        # Determine priority level
        if priority_score >= 80:
            priority_level = 'critical'
        elif priority_score >= 60:
            priority_level = 'high'
        elif priority_score >= 40:
            priority_level = 'medium'
        else:
            priority_level = 'low'
        
        ranked_list.append({
            'request': request,
            'priority_score': round(priority_score, 1),
            'priority_level': priority_level,
            'urgency_score': urgency_score,
            'time_score': time_score,
            'units_score': units_score,
            'blood_rarity_score': blood_rarity_score,
        })
    
    # Sort by priority score (highest first)
    ranked_list.sort(key=lambda x: x['priority_score'], reverse=True)
    
    return ranked_list


def calculate_urgency_score(urgency_level):
    """
    Convert urgency level to a score (0-100)
    """
    urgency_mapping = {
        'critical': 100,
        'urgent': 70,
        'normal': 40,
    }
    return urgency_mapping.get(urgency_level, 40)


def calculate_time_score(created_at):
    """
    Calculate score based on how long the request has been waiting
    Longer wait = higher score (0-100)
    FIX: Handle timezone-aware datetimes properly
    """
    # Make sure we're comparing timezone-aware datetimes
    now = timezone.now()  # This is timezone-aware
    
    # If created_at is naive, make it aware
    if timezone.is_naive(created_at):
        created_at = timezone.make_aware(created_at)
    
    time_waiting = now - created_at
    hours_waiting = time_waiting.total_seconds() / 3600
    
    # Score based on hours waiting
    # 0 hours = 0 points
    # 24+ hours = 100 points
    if hours_waiting >= 24:
        return 100
    elif hours_waiting >= 12:
        return 80
    elif hours_waiting >= 6:
        return 60
    elif hours_waiting >= 3:
        return 40
    elif hours_waiting >= 1:
        return 20
    else:
        return 0


def calculate_units_score(units_needed):
    """
    Calculate score based on units needed (0-100)
    More units = higher score
    """
    if units_needed >= 5:
        return 100
    elif units_needed >= 4:
        return 80
    elif units_needed >= 3:
        return 60
    elif units_needed >= 2:
        return 40
    else:
        return 20


def calculate_blood_rarity_score(blood_type):
    """
    Calculate score based on blood type rarity (0-100)
    Rarer blood types get higher scores
    """
    rarity_mapping = {
        'AB-': 100,  # Rarest
        'B-': 90,
        'AB+': 80,
        'A-': 70,
        'O-': 60,   # Universal donor but still rare
        'B+': 50,
        'A+': 40,
        'O+': 30,   # Most common
    }
    return rarity_mapping.get(blood_type, 50)