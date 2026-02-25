# donors/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from accounts.models import CustomUser
from .models import DonorProfile


class DonorRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'your.email@example.com'
    }))
    full_name = forms.CharField(max_length=200, required=True, widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Full Name'
    }))
    age = forms.IntegerField(
        required=True, min_value=18, max_value=65,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Age (18-65)'})
    )
    phone = forms.CharField(max_length=15, required=True, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': '9812345678', 'pattern': '[0-9]{10}'
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
            'class': 'form-control', 'rows': 2,
            'placeholder': 'City, District (e.g., Itahari, Sunsari)'
        })
    )
    weight = forms.FloatField(
        required=False, min_value=45,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Weight in kg (optional)'})
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'donor'
        user.email = self.cleaned_data['email']

        if commit:
            user.save()
            address = self.cleaned_data['address']
            lat, lon = geocode_address(address)
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
    Convert address string to (latitude, longitude).
    Covers all major Nepal cities/towns.
    Falls back to Kathmandu if no match found.
    """
    city_coordinates = {
        # Kathmandu Valley
        'kathmandu': (27.7172, 85.3240),
        'lalitpur':  (27.6667, 85.3167),
        'patan':     (27.6667, 85.3167),
        'bhaktapur': (27.6721, 85.4298),
        'kirtipur':  (27.6767, 85.2792),
        'pokhara':   (28.2096, 83.9856),

        # Eastern Nepal
        'biratnagar': (26.4525, 87.2718),
        'itahari':    (26.6641, 87.2796),
        'dharan':     (26.8125, 87.2833),
        'damak':      (26.6538, 87.6959),
        'birtamod':   (26.6458, 87.9934),
        'mechinagar': (26.6104, 87.9221),
        'ilam':       (26.9101, 87.9261),
        'urlabari':   (26.6333, 87.4167),
        'inaruwa':    (26.6237, 87.1479),
        'lahan':      (26.7230, 86.4808),
        'rajbiraj':   (26.5378, 86.7406),
        'siraha':     (26.6514, 86.2059),
        'gaur':       (26.7725, 85.2797),
        'janakpur':   (26.7288, 85.9242),

        # Central Nepal
        'hetauda':    (27.4287, 85.0328),
        'bharatpur':  (27.6764, 84.4336),
        'narayanghat':(27.6953, 84.4314),
        'birgunj':    (27.0000, 84.8833),
        'muglin':     (27.8583, 84.5295),
        'damauli':    (27.9667, 84.2833),
        'gorkha':     (28.0000, 84.6333),
        'tansen':     (27.8667, 83.5500),
        'butwal':     (27.7000, 83.4500),
        'bhairahawa': (27.5050, 83.4544),
        'siddharthanagar': (27.5050, 83.4544),

        # Western Nepal
        'nepalgunj':  (28.0500, 81.6167),
        'tulsipur':   (28.1333, 82.3000),
        'surkhet':    (28.5970, 81.6137),
        'birendranagar': (28.5970, 81.6137),
        'baglung':    (28.2667, 83.5833),
        'waling':     (28.0667, 83.7833),

        # Far-western Nepal
        'dhangadhi':  (28.6833, 80.6000),
        'mahendranagar': (28.9681, 80.1773),
        'dipayal':    (29.2653, 81.2108),
        'dadeldhura': (29.2975, 80.5786),
    }

    address_lower = address.lower()
    for city, coords in city_coordinates.items():
        if city in address_lower:
            return coords

    # Fallback: Kathmandu
    return (27.7172, 85.3240)


class DonorProfileUpdateForm(forms.ModelForm):
    """
    Form for donors to update their profile.
    Re-geocodes latitude/longitude automatically when address changes.
    """
    class Meta:
        model = DonorProfile
        fields = [
            'full_name', 'phone', 'address',
            'weight', 'is_available', 'medical_conditions'
        ]
        widgets = {
            'full_name':          forms.TextInput(attrs={'class': 'form-control'}),
            'phone':              forms.TextInput(attrs={'class': 'form-control', 'pattern': '[0-9]{10}'}),
            'address':            forms.Textarea(attrs={'class': 'form-control', 'rows': 2,
                                                        'placeholder': 'e.g. Itahari, Sunsari'}),
            'weight':             forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'is_available':       forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'medical_conditions': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
        labels = {
            'is_available':       'Available to donate',
            'medical_conditions': 'Medical Conditions (if any)',
        }

    def save(self, commit=True):
        profile = super().save(commit=False)

        # Re-geocode whenever address field changes
        if 'address' in self.changed_data:
            lat, lon = geocode_address(profile.address)
            profile.latitude = lat
            profile.longitude = lon

        if commit:
            profile.save()
        return profile