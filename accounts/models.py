from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ('donor', 'Donor'),
        ('hospital', 'Hospital'),
    )

    user_type = models.CharField(
        max_length=10,
        choices=USER_TYPE_CHOICES,
        default='donor'
    )
    email = models.EmailField(unique=True)

    failed_attempts = models.PositiveIntegerField(default=0)
    is_locked = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.username} ({self.user_type})"
