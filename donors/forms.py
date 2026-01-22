# donors/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from accounts.models import CustomUser
from .models import DonorProfile


class DonorRegisterForm(UserCreationForm):
    """
    Enhanced donor registration form with all required fields
    """
    # User fields
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'your.email@example.com'
    }))
    
    # Donor profile fields
    full_name = forms.CharField(max_length=200, required=True, widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Full Name'
    }))
    
    age = forms.IntegerField(
        required=True, 
        min_value=18, 
        max_value=65,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Age (18-65)'
        })
    )
    
    phone = forms.CharField(max_length=15, required=True, widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': '9812345678',
        'pattern': '[0-9]{10}'
    }))
    
    blood_type = forms.ChoiceField(
        choices=[
            ('', 'Select Blood Group'),
            ('A+', 'A+'), ('A-', 'A-'),
            ('B+', 'B+'), ('B-', 'B-'),
            ('O+', 'O+'), ('O-', 'O-'),
            ('AB+', 'AB+'), ('AB-', 'AB-'),
        ],
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    address = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'City, District (e.g., Kathmandu, Bagmati)'
        })
    )
    
    # Optional: Weight (useful for donation eligibility)
    weight = forms.FloatField(
        required=False,
        min_value=45,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Weight in kg (optional)'
        })
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2']

    def save(self, commit=True):
        """
        Create user and associated donor profile
        Automatically geocode address to get lat/lon (optional)
        """
        user = super().save(commit=False)
        user.user_type = 'donor'
        user.email = self.cleaned_data['email']
        
        if commit:
            user.save()
            
            # Get or estimate location coordinates
            address = self.cleaned_data['address']
            lat, lon = geocode_address(address)
            
            # Create donor profile
            DonorProfile.objects.create(
                user=user,
                full_name=self.cleaned_data['full_name'],
                age=self.cleaned_data['age'],
                phone=self.cleaned_data['phone'],
                blood_type=self.cleaned_data['blood_type'],
                address=address,
                latitude=lat,
                longitude=lon,
                weight=self.cleaned_data.get('weight'),
                is_available=True,
                donation_count=0,
            )
        
        return user


def geocode_address(address):
    """
    Convert address to latitude/longitude coordinates
    
    Options:
    1. Use Nominatim API (free, no API key needed)
    2. Use Google Maps Geocoding API (requires API key)
    3. Manual mapping for major Nepal cities (fallback)
    
    Returns:
        tuple: (latitude, longitude)
    """
    # Option 1: Manual mapping for major Nepal cities (simple fallback)
    city_coordinates = {
        'kathmandu': (27.7172, 85.3240),
        'pokhara': (28.2096, 83.9856),
        'lalitpur': (27.6667, 85.3167),
        'bhaktapur': (27.6721, 85.4298),
        'biratnagar': (26.4525, 87.2718),
        'bharatpur': (27.6764, 84.4336),
        'birgunj': (27.0000, 84.8833),
        'dharan': (26.8125, 87.2833),
        'hetauda': (27.4287, 85.0328),
        'janakpur': (26.7288, 85.9242),
    }
    
    # Check if address contains any major city
    address_lower = address.lower()
    for city, coords in city_coordinates.items():
        if city in address_lower:
            return coords
    
    # Default to Kathmandu if no match
    return (27.7172, 85.3240)
    
    # Option 2: Use Nominatim API (uncomment to use)
    """
    try:
        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent="lifelink_nepal")
        location = geolocator.geocode(f"{address}, Nepal")
        
        if location:
            return (location.latitude, location.longitude)
    except:
        pass
    
    # Fallback to Kathmandu
    return (27.7172, 85.3240)
    """


class DonorProfileUpdateForm(forms.ModelForm):
    """
    Form for donors to update their profile information
    """
    class Meta:
        model = DonorProfile
        fields = [
            'full_name', 'phone', 'address', 
            'weight', 'is_available', 'medical_conditions'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'pattern': '[0-9]{10}'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'is_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'medical_conditions': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
        labels = {
            'is_available': 'Available to donate',
            'medical_conditions': 'Medical Conditions (if any)',
        }
    
    def save(self, commit=True):
        """Update location coordinates when address changes"""
        profile = super().save(commit=False)
        
        # Re-geocode if address changed
        if 'address' in self.changed_data:
            lat, lon = geocode_address(profile.address)
            profile.latitude = lat
            profile.longitude = lon
        
        if commit:
            profile.save()
        
        return profile