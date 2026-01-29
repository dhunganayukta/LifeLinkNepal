from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
import getpass

User = get_user_model()

class Command(BaseCommand):
    help = 'Create a superuser with secret key only'

    def handle(self, *args, **options):
        # Ask for secret key
        secret = getpass.getpass('Enter SUPERUSER SECRET KEY: ')

        expected_secret = getattr(settings, 'SUPERUSER_SECRET_KEY', None)
        if secret != expected_secret:
            self.stdout.write(self.style.ERROR('Invalid secret key. Cannot create superuser.'))
            return

        # Ask for username, email, password
        username = input('Username: ')
        email = input('Email: ')
        password = getpass.getpass('Password: ')

        # Check if username exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.ERROR('User with this username already exists.'))
            return

        # Create superuser
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )

        self.stdout.write(self.style.SUCCESS(f'Superuser {username} created successfully!'))
