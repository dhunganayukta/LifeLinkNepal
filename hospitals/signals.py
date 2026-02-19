# hospitals/signals.py (NEW FILE - Create this)
"""
Signals to automatically notify donors when blood request is created
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from hospitals.models import BloodRequest
from donors.tasks import notify_first_donor


@receiver(post_save, sender=BloodRequest)
def auto_notify_first_donor(sender, instance, created, **kwargs):
    """
    Automatically notify the first donor when a new blood request is created
    """
    if created and instance.status == 'pending':
        # Trigger Celery task to notify first donor
        notify_first_donor.delay(instance.id)
        print(f"🔔 Auto-notification triggered for BloodRequest #{instance.id}")