from django.contrib.auth.models import AbstractUser
from django.db import models
from datetime import datetime, timedelta
from django.utils import timezone

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ('donor', 'Donor'),
        ('hospital', 'Hospital'),
        ('super_admin', 'Super Admin'),
    )

    user_type = models.CharField(
        max_length=15,
        choices=USER_TYPE_CHOICES,
        default='donor'
    )
    email = models.EmailField(unique=True)

    failed_attempts = models.PositiveIntegerField(default=0)
    is_locked = models.BooleanField(default=False)
    
    # 🔥 NEW: Password expiration fields
    password_changed_at = models.DateTimeField(default=timezone.now)
    password_expires_days = models.PositiveIntegerField(default=365)  # 1 year

    def __str__(self):
        return f"{self.username} ({self.user_type})"
    
    # 🔥 NEW: Check if password has expired
    def is_password_expired(self):
        """Returns True if password has expired"""
        if not self.password_changed_at:
            return False
        
        expiry_date = self.password_changed_at + timedelta(days=self.password_expires_days)
        return timezone.now() > expiry_date
    
    # 🔥 NEW: Override set_password to update password_changed_at
    def set_password(self, raw_password):
        super().set_password(raw_password)
        self.password_changed_at = timezone.now()
