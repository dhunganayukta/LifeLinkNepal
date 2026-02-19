# accounts/backends.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


class EmailBackend(ModelBackend):
    """
    Custom authentication backend that allows users to log in with email OR username
    Compatible with Django admin
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        
        try:
            # Try to find user by email OR username
            user = User.objects.get(Q(email=username) | Q(username=username))
        except User.DoesNotExist:
            # Run the default password hasher once to reduce timing attack
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:
            # If multiple users, try username first, then email
            user = User.objects.filter(username=username).first()
            if not user:
                user = User.objects.filter(email=username).first()
        
        # Check password and verify user is active
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
    
    def user_can_authenticate(self, user):
        """
        Reject users with is_active=False. Custom user models that don't have
        an `is_active` field are allowed.
        """
        return getattr(user, 'is_active', True)