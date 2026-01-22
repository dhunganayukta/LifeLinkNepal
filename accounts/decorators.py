from django.shortcuts import redirect
from functools import wraps

def user_type_required(required_type):
    """
    Generic decorator: protects a view based on user_type
    Example: @user_type_required('donor')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated or request.user.user_type != required_type:
                return redirect('login')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
