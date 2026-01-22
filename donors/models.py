# donors/models.py
from django.db import models
from django.conf import settings


class DonorProfile(models.Model):
    BLOOD_TYPE_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=200)
    age = models.IntegerField()
    phone = models.CharField(max_length=15)  # Added
    blood_type = models.CharField(max_length=3, choices=BLOOD_TYPE_CHOICES)
    address = models.TextField()
    
    # Geolocation
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    # Donation tracking
    donation_count = models.IntegerField(default=0)
    last_donation_date = models.DateField(null=True, blank=True)
    is_available = models.BooleanField(default=True, help_text="Available to donate")
    
    # Health info
    weight = models.FloatField(null=True, blank=True, help_text="Weight in kg")  # Added
    medical_conditions = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.full_name} ({self.blood_type})"
    
    @property
    def can_donate(self):
        """Check if donor is eligible to donate (90 days since last donation)"""
        if not self.last_donation_date:
            return True
        
        from datetime import date
        days_since = (date.today() - self.last_donation_date).days
        return days_since >= 90
    
    class Meta:
        verbose_name = 'Donor Profile'
        verbose_name_plural = 'Donor Profiles'


class Notification(models.Model):
    """Notifications for donors"""
    donor = models.ForeignKey(DonorProfile, on_delete=models.CASCADE, related_name='notifications')
    blood_request = models.ForeignKey('hospitals.BloodRequest', on_delete=models.CASCADE, null=True, blank=True)
    
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    responded = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Notification for {self.donor.full_name}"
    
    class Meta:
        ordering = ['-created_at']


class DonationHistory(models.Model):
    """Track donation history"""
    donor = models.ForeignKey(DonorProfile, on_delete=models.CASCADE, related_name='donation_history')
    hospital = models.ForeignKey('hospitals.HospitalProfile', on_delete=models.CASCADE, null=True, blank=True)
    blood_request = models.ForeignKey('hospitals.BloodRequest', on_delete=models.SET_NULL, null=True, blank=True)
    
    date_donated = models.DateField()
    units_donated = models.IntegerField(default=1)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.donor.full_name} - {self.date_donated}"
    
    class Meta:
        ordering = ['-date_donated']
        verbose_name = 'Donation History'
        verbose_name_plural = 'Donation Histories'