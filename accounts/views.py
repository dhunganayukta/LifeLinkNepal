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
from donors.models import DonorProfile
from hospitals.models import HospitalProfile
from accounts.decorators import role_required

User = get_user_model()

# -----------------------------
# HELPER: JWT TOKEN GENERATOR
# -----------------------------
def get_tokens_for_user(user):
    """
    Generate JWT tokens and embed role in payload
    """
    refresh = RefreshToken.for_user(user)
    refresh['user_type'] = user.user_type
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

def register_page(request):
    """
    Renders the registration page
    """
    return render(request, 'accounts/register.html')

def login_page(request):
    """
    Renders the login page
    """
    return render(request, 'accounts/login.html')

# -----------------------------
# REGISTER API
# -----------------------------
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

    # -----------------------------
    # BASIC USER VALIDATION
    # -----------------------------
    if user_type not in ['donor', 'hospital']:
        return Response({"error": "Invalid user type"}, status=400)

    if not all([username, password, email]):
        return Response({"error": "Username, email and password are required"}, status=400)

    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already exists"}, status=400)

    if User.objects.filter(email=email).exists():
        return Response({"error": "Email already registered"}, status=400)

    # -----------------------------
    # DONOR VALIDATION (BEFORE USER CREATION)
    # -----------------------------
    if user_type == 'donor':
        donor_required = ['full_name', 'age', 'phone', 'blood_type', 'address']
        for field in donor_required:
            if not request.data.get(field):
                return Response(
                    {"error": f"{field} is required for donor registration"},
                    status=400
                )

    # -----------------------------
    # HOSPITAL VALIDATION
    # -----------------------------
    if user_type == 'hospital':
        hospital_required = ['hospital_name', 'phone', 'address']
        for field in hospital_required:
            if not request.data.get(field):
                return Response(
                    {"error": f"{field} is required for hospital registration"},
                    status=400
                )

    # -----------------------------
    # CREATE USER
    # -----------------------------
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        user_type=user_type
    )

    # -----------------------------
    # CREATE PROFILE
    # -----------------------------
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

    # -----------------------------
    # JWT TOKENS
    # -----------------------------
    tokens = get_tokens_for_user(user)

    return Response(
        {
            "message": "Registration successful",
            "tokens": tokens,
            "user_type": user.user_type
        },
        status=status.HTTP_201_CREATED
    )


# -----------------------------
# LOGIN API
# -----------------------------
@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    JWT login with account lock after 5 failed attempts
    """
    username = request.data.get('username')
    password = request.data.get('password')

    user = User.objects.filter(username=username).first()

    if not user:
        raise AuthenticationFailed("Invalid credentials")

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

    # Use the authenticated user object for tokens/session
    tokens = get_tokens_for_user(user_auth)

    # Store tokens in the Django session so browser-based flows can access them
    if hasattr(request, 'session'):
        request.session['access_token'] = tokens.get('access')
        request.session['refresh_token'] = tokens.get('refresh')
        # Optional: set session expiry to match access token lifetime if desired
        # request.session.set_expiry(60 * 60)  # e.g. 1 hour

    # Also log the user into Django's session framework (for template-based views)
    try:
        auth_login(request, user_auth)
    except Exception:
        # If session login fails for any reason, continue — tokens are still returned
        pass

    return Response({
        "message": "Login successful",
        "tokens": tokens,
        "user_type": user_auth.user_type
    })

# -----------------------------
# DONOR DASHBOARD API
# -----------------------------
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

# -----------------------------
# HOSPITAL DASHBOARD API
# -----------------------------
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
# -----------------------------
# TEMPLATE LOGIN PAGE
# -----------------------------
def login_page(request):
    """
    Renders a login page for browser users
    """
    return render(request, 'accounts/login.html')


# -----------------------------
# TEMPLATE LOGOUT
# -----------------------------
def logout_view(request):
    """
    Logs out the user from the session
    """
    auth_logout(request)
    return redirect('home')