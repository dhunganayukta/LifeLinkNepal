from django.contrib.auth import authenticate, get_user_model
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import AuthenticationFailed

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

    # Basic validation
    if user_type not in ['donor', 'hospital']:
        return Response({"error": "Invalid user type"}, status=status.HTTP_400_BAD_REQUEST)
    if not all([username, password, email]):
        return Response({"error": "All fields are required"}, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(email=email).exists():
        return Response({"error": "Email already registered"}, status=status.HTTP_400_BAD_REQUEST)

    # Create user
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        user_type=user_type
    )

    # Create profile
    if user_type == 'donor':
        DonorProfile.objects.create(user=user)
    else:
        hospital_name = request.data.get('hospital_name')
        phone = request.data.get('phone')
        address = request.data.get('address')
        if not all([hospital_name, phone, address]):
            user.delete()
            return Response({"error": "All hospital fields are required"}, status=status.HTTP_400_BAD_REQUEST)
        HospitalProfile.objects.create(
            user=user,
            hospital_name=hospital_name,
            phone=phone,
            address=address
        )

    tokens = get_tokens_for_user(user)

    return Response({
        "message": "Registration successful",
        "tokens": tokens,
        "user_type": user.user_type
    }, status=status.HTTP_201_CREATED)

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

    tokens = get_tokens_for_user(user)

    return Response({
        "message": "Login successful",
        "tokens": tokens,
        "user_type": user.user_type
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
