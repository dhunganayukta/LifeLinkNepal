from django.contrib.auth import authenticate, get_user_model, login as auth_login
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import AuthenticationFailed
from django.shortcuts import render, redirect
from django.contrib.auth import logout as auth_logout
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings  # ✅ ADDED
from donors.models import DonorProfile
from hospitals.models import HospitalProfile
from accounts.decorators import role_required
import os

User = get_user_model()

# ========================================
# ADMIN SECRET KEY (from Django settings)
# ========================================
ADMIN_SECRET_KEY = getattr(settings, 'ADMIN_SECRET_KEY', None)  # ✅ ADDED

# ========================================
# HELPER: JWT TOKEN GENERATOR
# ========================================
def get_tokens_for_user(user):
    """
    Generate JWT tokens and embed role in payload
    """
    refresh = RefreshToken.for_user(user)
    refresh['user_type'] = user.user_type if hasattr(user, 'user_type') else 'super_admin'
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

# ========================================
# PAGE VIEWS
# ========================================
def register_page(request):
    """Renders the registration page"""
    return render(request, 'accounts/register.html')

def login_page(request):
    """Renders the login page"""
    return render(request, 'accounts/login.html')

def admin_register_page(request):
    """Renders the admin registration page"""
    return render(request, 'admin_register.html')

def admin_login_page(request):
    """Renders the admin login page"""
    return render(request, 'admin_login.html')

# ========================================
# ADMIN REGISTRATION API (WITH SECRET KEY)
# ========================================
@api_view(['POST'])
@permission_classes([AllowAny])
def admin_register(request):
    """
    Register a new admin user - Requires secret key
    """
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')
    secret_key = request.data.get('secret_key')
    
    # Validate required fields
    if not all([username, email, password, secret_key]):
        return Response({
            'error': 'All fields are required: username, email, password, secret_key'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Verify secret key
    if secret_key != ADMIN_SECRET_KEY:
        return Response({
            'error': '🔒 Invalid secret key. Only authorized personnel can create admin accounts.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Check if username already exists
    if User.objects.filter(username=username).exists():
        return Response({
            'error': 'Username already exists'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if email already exists
    if User.objects.filter(email=email).exists():
        return Response({
            'error': 'Email already exists'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Create admin user (staff + superuser)
        admin_user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        
        # Make them staff and superuser
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()
        
        return Response({
            'message': '✅ Admin account created successfully!',
            'username': username,
            'email': email,
            'is_staff': True,
            'is_superuser': True
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'error': f'Failed to create admin account: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ========================================
# ADMIN LOGIN API
# ========================================
@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login(request):
    """
    Login for admin users - Only allows staff users to login
    """
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response({
            'error': 'Please provide both username and password'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Authenticate user
    user = authenticate(username=username, password=password)
    
    if user is None:
        return Response({
            'detail': 'Invalid username or password'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    # Check if user is staff/superuser (admin)
    if not (user.is_staff or user.is_superuser):
        return Response({
            'detail': '⛔ Access denied. This login is for administrators only.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Check if user is active
    if not user.is_active:
        return Response({
            'detail': 'Account is disabled'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Generate JWT tokens
    tokens = get_tokens_for_user(user)
    
    # Store tokens in session
    if hasattr(request, 'session'):
        request.session['access_token'] = tokens.get('access')
        request.session['refresh_token'] = tokens.get('refresh')
    
    # Log user into Django session
    try:
        auth_login(request, user)
    except Exception:
        pass
    
    # Return success response
    return Response({
        'message': 'Admin login successful',
        'access': tokens['access'],
        'refresh': tokens['refresh'],
        'user_type': 'super_admin',
        'is_staff': True,
        'is_superuser': user.is_superuser,
        'username': user.username,
        'email': user.email,
        'profile': {
            'username': user.username,
            'email': user.email,
            'is_staff': True,
            'is_superuser': user.is_superuser,
        }
    }, status=status.HTTP_200_OK)

# ========================================
# REGISTER API (DONOR & HOSPITAL)
# ========================================
@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    Registers donor or hospital and returns JWT tokens
    """
    user_type = request.data.get('user_type')
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email')

    # Basic validation
    if user_type not in ['donor', 'hospital']:
        return Response({"error": "Invalid user type"}, status=400)

    if not all([username, password, email]):
        return Response({"error": "Username, email and password are required"}, status=400)

    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already exists"}, status=400)

    if User.objects.filter(email=email).exists():
        return Response({"error": "Email already registered"}, status=400)

    # Donor validation
    if user_type == 'donor':
        donor_required = ['full_name', 'age', 'phone', 'blood_type', 'address']
        for field in donor_required:
            if not request.data.get(field):
                return Response(
                    {"error": f"{field} is required for donor registration"},
                    status=400
                )

    # Hospital validation
    if user_type == 'hospital':
        hospital_required = ['hospital_name', 'phone', 'address']
        for field in hospital_required:
            if not request.data.get(field):
                return Response(
                    {"error": f"{field} is required for hospital registration"},
                    status=400
                )

    # Create user
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        user_type=user_type
    )

    # Create profile
    if user_type == 'donor':
        DonorProfile.objects.create(
            user=user,
            full_name=request.data['full_name'],
            age=int(request.data['age']),
            phone=request.data['phone'],
            blood_type=request.data['blood_type'],
            address=request.data['address'],
            weight=request.data.get('weight'),
            medical_conditions=request.data.get('medical_conditions', '')
        )
    else:  # hospital
        HospitalProfile.objects.create(
            user=user,
            hospital_name=request.data['hospital_name'],
            phone=request.data['phone'],
            address=request.data['address']
        )

    # JWT tokens
    tokens = get_tokens_for_user(user)

    return Response(
        {
            "message": "Registration successful",
            "tokens": tokens,
            "user_type": user.user_type
        },
        status=status.HTTP_201_CREATED
    )

# ========================================
# LOGIN API (DONOR & HOSPITAL)
# ========================================
@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    JWT login for donor and hospital users
    (Admin users should use /admin/login/ instead)
    """
    username = request.data.get('username')
    password = request.data.get('password')

    user = User.objects.filter(username=username).first()

    if not user:
        raise AuthenticationFailed("Invalid credentials")

    # ✅ BLOCK ADMIN USERS FROM REGULAR LOGIN
    if user.is_staff or user.is_superuser:
        return Response({
            'detail': '⛔ Please use the admin login page for administrator accounts.',
            'redirect': '/accounts/admin/login-page/'
        }, status=status.HTTP_403_FORBIDDEN)

    if user.is_locked:
        raise AuthenticationFailed("Account locked due to multiple failed attempts")

    # Check password
    user_auth = authenticate(username=username, password=password)
    if user_auth is None:
        # Increment failed attempts
        user.failed_attempts += 1
        if user.failed_attempts >= 5:
            user.is_locked = True
        user.save()
        raise AuthenticationFailed("Invalid credentials")

    # Reset failed attempts
    user.failed_attempts = 0
    user.save()

    # Generate tokens
    tokens = get_tokens_for_user(user_auth)

    # Store tokens in session
    if hasattr(request, 'session'):
        request.session['access_token'] = tokens.get('access')
        request.session['refresh_token'] = tokens.get('refresh')

    # Log user into Django session
    try:
        auth_login(request, user_auth)
    except Exception:
        pass

    # Return response with is_staff status
    return Response({
        "message": "Login successful",
        "access": tokens['access'],
        "refresh": tokens['refresh'],
        "user_type": user_auth.user_type,
        "is_staff": False,  # ✅ Always False for regular users
        "is_superuser": False,
        "username": user_auth.username,
        "email": user_auth.email
    })

# ========================================
# DONOR DASHBOARD API
# ========================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@role_required('donor')
def donor_dashboard(request):
    donor_profile = getattr(request.user, 'donorprofile', None)
    if not donor_profile:
        return Response({"error": "Donor profile not found"}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        "username": request.user.username,
        "blood_group": donor_profile.blood_group,
        "last_donation": donor_profile.last_donation,
        "total_units": donor_profile.total_units_donated,
        "donations_history": [
            {
                "hospital": d.hospital.hospital_name,
                "date": d.date,
                "units": d.units
            } for d in donor_profile.donations.all()
        ]
    })

# ========================================
# HOSPITAL DASHBOARD API
# ========================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@role_required('hospital')
def hospital_dashboard(request):
    hospital_profile = getattr(request.user, 'hospitalprofile', None)
    if not hospital_profile:
        return Response({"error": "Hospital profile not found"}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        "username": request.user.username,
        "hospital_name": hospital_profile.hospital_name,
        "blood_requests_sent": hospital_profile.requests_sent.count(),
        "top_donors": [
            {
                "username": d.donor.user.username,
                "blood_group": d.donor.blood_group,
                "donated_at": d.date
            } for d in hospital_profile.highest_donors()
        ]
    })

# ========================================
# LOGOUT
# ========================================
def logout_view(request):
    """Logs out the user from the session"""
    auth_logout(request)
    return redirect('home')