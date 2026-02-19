# lifelink/celery.py (NEW FILE - Create this in your project root)
"""
Celery configuration for automatic background tasks
"""
import os
from celery import Celery

# Set default Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lifelink.settings')

# Create Celery app
app = Celery('lifelink')

# Load config from Django settings (prefix: CELERY_)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')