# hospitals/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone


class HospitalProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    hospital_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=15)
    address = models.TextField()
    
    # Geolocation (you can auto-populate these from address using geocoding API)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    license_number = models.CharField(max_length=100, blank=True)
    is_verified = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.hospital_name
    
    class Meta:
        verbose_name = 'Hospital Profile'
        verbose_name_plural = 'Hospital Profiles'


class BloodRequest(models.Model):
    URGENCY_CHOICES = [
        ('critical', 'Critical - Life Threatening'),
        ('urgent', 'Urgent - Within 24 Hours'),
        ('normal', 'Normal - Within 48 Hours'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('fulfilled', 'Fulfilled'),
        ('cancelled', 'Cancelled'),
    ]
    
    BLOOD_TYPE_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
    ]
    
    hospital = models.ForeignKey(HospitalProfile, on_delete=models.CASCADE, related_name='blood_requests')
    blood_type = models.CharField(max_length=3, choices=BLOOD_TYPE_CHOICES)
    units_needed = models.IntegerField(default=1)
    urgency_level = models.CharField(max_length=10, choices=URGENCY_CHOICES, default='normal')
    
    patient_name = models.CharField(max_length=200)
    patient_age = models.IntegerField(null=True, blank=True)
    condition = models.TextField(blank=True, help_text="Patient's medical condition")
    notes = models.TextField(blank=True)
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    required_by = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.hospital.hospital_name} - {self.blood_type} ({self.urgency_level})"
    
    @property
    def hours_waiting(self):
        """Calculate how many hours this request has been pending"""
        delta = timezone.now() - self.created_at
        return delta.total_seconds() / 3600
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Blood Request'
        verbose_name_plural = 'Blood Requests'


class DonorNotification(models.Model):
    """Track which donors were notified for each blood request"""
    # Use string reference to avoid circular import
    donor = models.ForeignKey('donors.DonorProfile', on_delete=models.CASCADE, related_name='hospital_notifications')
    blood_request = models.ForeignKey(BloodRequest, on_delete=models.CASCADE, related_name='notified_donors')
    
    match_score = models.FloatField(help_text="MCDM match score (0-1)")
    distance = models.FloatField(help_text="Distance in km")
    
    is_read = models.BooleanField(default=False)
    responded = models.BooleanField(default=False)
    
    sent_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.donor.full_name} notified for {self.blood_request}"
    
    class Meta:
        ordering = ['-sent_at']


class DonorResponse(models.Model):
    """Track donor responses to blood requests"""
    STATUS_CHOICES = [
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('completed', 'Donation Completed'),
    ]
    
    # Use string reference to avoid circular import
    donor = models.ForeignKey('donors.DonorProfile', on_delete=models.CASCADE, related_name='hospital_responses')
    blood_request = models.ForeignKey(BloodRequest, on_delete=models.CASCADE, related_name='donor_responses')
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    response_notes = models.TextField(blank=True)
    
    responded_at = models.DateTimeField(auto_now_add=True)
    donation_completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.donor.full_name} - {self.status}"
    
    class Meta:
        ordering = ['-responded_at']