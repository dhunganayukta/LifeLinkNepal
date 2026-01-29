from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from rest_framework.exceptions import PermissionDenied, NotAuthenticated

def role_required(required_role):
    """
    Role-based decorator that works for both REST API and Django template views
    Automatically detects the type of view and responds appropriately
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user

            # Check if it's an API request (you can adjust this logic based on your URL patterns)
            is_api_request = (
                request.path.startswith('/api/') or 
                request.content_type == 'application/json' or
                'application/json' in request.META.get('HTTP_ACCEPT', '')
            )

            # Check authentication
            if not user or not user.is_authenticated:
                if is_api_request:
                    raise NotAuthenticated("Authentication required")
                else:
                    messages.error(request, "Please log in to access this page.")
                    return redirect('accounts:login_page')  # Update to your login URL name

            # Check role/user_type
            if user.user_type != required_role:
                if is_api_request:
                    raise PermissionDenied("Access denied")
                else:
                    messages.error(request, f"Access denied. This page is for {required_role}s only.")
                    return redirect('home')  # Update to your home URL name

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# REST API Token serializer
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['user_type'] = user.user_type
        token['username'] = user.username
        return token