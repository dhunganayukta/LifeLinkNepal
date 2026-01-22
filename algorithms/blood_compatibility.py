"""
Blood Type Compatibility Helper
Determines which donor blood types can donate to which recipient blood types
"""

# Blood type compatibility matrix
COMPATIBILITY = {
    'O-': ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+'],  # Universal donor
    'O+': ['O+', 'A+', 'B+', 'AB+'],
    'A-': ['A-', 'A+', 'AB-', 'AB+'],
    'A+': ['A+', 'AB+'],
    'B-': ['B-', 'B+', 'AB-', 'AB+'],
    'B+': ['B+', 'AB+'],
    'AB-': ['AB-', 'AB+'],
    'AB+': ['AB+'],  # Universal recipient
}


def is_compatible(donor_blood_type, recipient_blood_type):
    """
    Check if donor blood type is compatible with recipient
    
    Args:
        donor_blood_type: Donor's blood type (e.g., 'O+')
        recipient_blood_type: Recipient's blood type (e.g., 'A+')
    
    Returns:
        Boolean: True if compatible, False otherwise
    """
    if donor_blood_type not in COMPATIBILITY:
        return False
    
    return recipient_blood_type in COMPATIBILITY[donor_blood_type]


def get_compatible_donors(recipient_blood_type):
    """
    Get list of blood types that can donate to recipient
    
    Args:
        recipient_blood_type: Recipient's blood type
    
    Returns:
        List of compatible donor blood types
    """
    compatible_donors = []
    
    for donor_type, recipients in COMPATIBILITY.items():
        if recipient_blood_type in recipients:
            compatible_donors.append(donor_type)
    
    return compatible_donors


def get_compatible_recipients(donor_blood_type):
    """
    Get list of blood types that can receive from donor
    
    Args:
        donor_blood_type: Donor's blood type
    
    Returns:
        List of compatible recipient blood types
    """
    return COMPATIBILITY.get(donor_blood_type, [])