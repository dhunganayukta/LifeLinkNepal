# api/serializers.py - EXACT MATCH FOR YOUR MODELS

from rest_framework import serializers
from donors.models import DonorProfile, DonorNotification, DonationHistory
from hospitals.models import HospitalProfile, BloodRequest


class DonorSerializer(serializers.ModelSerializer):
    """
    Serializer for DonorProfile with ALL fields needed for dashboard
    """
    # Add computed field for email from user
    email = serializers.EmailField(source='user.email', read_only=True)
    
    # Rename address to location for frontend compatibility
    location = serializers.CharField(source='address', read_only=True)
    
    class Meta:
        model = DonorProfile
        fields = [
            'id',
            'full_name',
            'age',
            'phone',
            'blood_type',
            'address',           # Original field name
            'location',          # Alias for 'address' (for frontend)
            'latitude',
            'longitude',
            'donation_count',
            'last_donation_date',
            'is_available',
            'email',             # From user relationship
            'created_at',
            'updated_at',
        ]


class HospitalSerializer(serializers.ModelSerializer):
    """
    Serializer for HospitalProfile with ALL fields needed for dashboard
    """
    # Add computed field for email from user
    email = serializers.EmailField(source='user.email', read_only=True)
    
    # Rename hospital_name to name for frontend compatibility
    name = serializers.CharField(source='hospital_name', read_only=True)
    
    # Rename address to location for frontend compatibility
    location = serializers.CharField(source='address', read_only=True)
    
    class Meta:
        model = HospitalProfile
        fields = [
            'id',
            'hospital_name',     # Original field name
            'name',              # Alias for 'hospital_name' (for frontend)
            'phone',
            'address',           # Original field name
            'location',          # Alias for 'address' (for frontend)
            'latitude',
            'longitude',
            'license_number',
            'is_verified',
            'email',             # From user relationship
            'created_at',
            'updated_at',
        ]


class BloodRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for BloodRequest with hospital details
    """
    # Include hospital details
    hospital_name = serializers.CharField(source='hospital.hospital_name', read_only=True)
    hospital_location = serializers.CharField(source='hospital.address', read_only=True)
    hospital_phone = serializers.CharField(source='hospital.phone', read_only=True)
    
    # Rename urgency_level to urgency for frontend compatibility
    urgency = serializers.CharField(source='urgency_level', read_only=True)
    
    class Meta:
        model = BloodRequest
        fields = [
            'id',
            'hospital',
            'hospital_name',
            'hospital_location',
            'hospital_phone',
            'blood_type',
            'units_needed',
            'urgency_level',     # Original field name
            'urgency',           # Alias for 'urgency_level' (for frontend)
            'patient_name',
            'patient_age',
            'condition',
            'notes',
            'status',
            'created_at',
            'updated_at',
            'required_by',
        ]


class DonorNotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for DonorNotification with donor and request details
    """
    donor_name = serializers.CharField(source='donor.full_name', read_only=True)
    donor_blood_type = serializers.CharField(source='donor.blood_type', read_only=True)
    donor_phone = serializers.CharField(source='donor.phone', read_only=True)
    donor_location = serializers.CharField(source='donor.address', read_only=True)
    
    request_blood_type = serializers.CharField(source='blood_request.blood_type', read_only=True)
    request_urgency = serializers.CharField(source='blood_request.urgency_level', read_only=True)
    hospital_name = serializers.CharField(source='blood_request.hospital.hospital_name', read_only=True)
    
    class Meta:
        model = DonorNotification
        fields = [
            'id',
            'donor',
            'donor_name',
            'donor_blood_type',
            'donor_phone',
            'donor_location',
            'blood_request',
            'request_blood_type',
            'request_urgency',
            'hospital_name',
            'match_score',
            'distance',
            'is_read',
            'responded',
            'sent_at',
            'is_notified',
            'priority_order',
            'status',
            'notified_at',
            'responded_at',
            'response_notes',
        ]


class DonationHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for DonationHistory
    """
    donor_name = serializers.CharField(source='donor.full_name', read_only=True)
    hospital_name = serializers.CharField(source='hospital.hospital_name', read_only=True)
    
    class Meta:
        model = DonationHistory
        fields = [
            'id',
            'donor',
            'donor_name',
            'hospital',
            'hospital_name',
            'blood_request',
            'date_donated',
            'units_donated',
            'notes',
            'created_at',
        ]