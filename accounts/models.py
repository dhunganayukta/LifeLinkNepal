# accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ('donor', 'Donor'),
        ('hospital', 'Hospital'),
    )
    
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='donor')
    email = models.EmailField(unique=True)
    
    def __str__(self):
        return f"{self.username} ({self.user_type})"
    
    # Helper properties for template checks
    @property
    def is_donor(self):
        return self.user_type == 'donor'
    
    @property
    def is_hospital(self):
        return self.user_type == 'hospital'
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'