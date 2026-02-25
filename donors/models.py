from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


# ---------------------------
# Donor Profile
# ---------------------------
class DonorProfile(models.Model):
    BLOOD_TYPE_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='donor_profile'
    )

    full_name = models.CharField(max_length=200)
    age = models.PositiveIntegerField(
        validators=[MinValueValidator(18), MaxValueValidator(65)]
    )
    phone = models.CharField(max_length=15, db_index=True)
    blood_type = models.CharField(max_length=4, choices=BLOOD_TYPE_CHOICES)
    address = models.TextField()

    # Geolocation (optional)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    # Donation tracking
    donation_count = models.PositiveIntegerField(default=0)
    points = models.PositiveIntegerField(default=0)          # ← ADDED
    last_donation_date = models.DateField(null=True, blank=True)
    is_available = models.BooleanField(default=True)

    # Health info (optional)
    weight = models.FloatField(null=True, blank=True)
    medical_conditions = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def can_donate(self) -> bool:
        """Donors can donate every 90 days"""
        from datetime import date
        if not self.last_donation_date:
            return True
        return (date.today() - self.last_donation_date).days >= 90

    def __str__(self):
        return f"{self.full_name} ({self.blood_type})"

    class Meta:
        verbose_name = "Donor Profile"
        verbose_name_plural = "Donor Profiles"
        ordering = ['-created_at']


class DonorNotification(models.Model):
    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('notified',  'Notified'),
        ('accepted',  'Accepted'),
        ('rejected',  'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    donor = models.ForeignKey(
        DonorProfile,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    blood_request = models.ForeignKey(
        'hospitals.BloodRequest',
        on_delete=models.CASCADE,
        related_name='donor_notifications'
    )

    match_score = models.FloatField(null=True, blank=True)
    distance = models.FloatField(null=True, blank=True)

    is_read = models.BooleanField(default=False)
    responded = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)

    is_notified = models.BooleanField(default=False)
    priority_order = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notified_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    response_notes = models.TextField(blank=True)

    def __str__(self):
        return f"Notification → {self.donor.full_name} | Request #{self.blood_request_id} (Priority: {self.priority_order})"

    @property
    def response_time_hours(self):
        if self.notified_at and self.responded_at:
            delta = self.responded_at - self.notified_at
            return round(delta.total_seconds() / 3600, 2)
        return None

    class Meta:
        ordering = ['priority_order', '-sent_at']
        indexes = [
            models.Index(fields=['blood_request', 'status']),
            models.Index(fields=['donor', '-sent_at']),
            models.Index(fields=['blood_request', 'priority_order']),
        ]


class DonorResponse(models.Model):
    STATUS_CHOICES = [
        ('accepted',  'Accepted'),
        ('declined',  'Declined'),
        ('completed', 'Donation Completed'),
    ]

    donor = models.ForeignKey(
        DonorProfile,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    blood_request = models.ForeignKey(
        'hospitals.BloodRequest',
        on_delete=models.CASCADE,
        related_name='donor_responses'
    )

    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    response_notes = models.TextField(blank=True)
    responded_at = models.DateTimeField(auto_now_add=True)
    donation_completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.donor.full_name} → {self.status}"

    class Meta:
        ordering = ['-responded_at']


class DonationHistory(models.Model):
    donor = models.ForeignKey(
        DonorProfile,
        on_delete=models.CASCADE,
        related_name='donation_history'
    )
    hospital = models.ForeignKey(
        'hospitals.HospitalProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    blood_request = models.ForeignKey(
        'hospitals.BloodRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    date_donated = models.DateField()
    units_donated = models.PositiveIntegerField(default=1)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.donor.full_name} | {self.date_donated}"

    class Meta:
        ordering = ['-date_donated']
        verbose_name = "Donation History"
        verbose_name_plural = "Donation Histories"