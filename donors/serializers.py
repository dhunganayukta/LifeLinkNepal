# donors/serializers.py
from rest_framework import serializers
from .models import DonorProfile, DonorNotification, DonorResponse, DonationHistory


class DonorSerializer(serializers.ModelSerializer):
    email = serializers.SerializerMethodField()
    
    class Meta:
        model = DonorProfile
        fields = [
            'id', 'full_name', 'email', 'age', 'phone', 'blood_type', 
            'address', 'latitude', 'longitude', 'donation_count', 
            'last_donation_date', 'is_available', 'weight', 
            'medical_conditions', 'created_at', 'updated_at', 'can_donate'
        ]
    
    def get_email(self, obj):
        return obj.user.email if obj.user else "N/A"


class DonorNotificationSerializer(serializers.ModelSerializer):
    donor_name = serializers.CharField(source='donor.full_name', read_only=True)
    donor_blood_type = serializers.CharField(source='donor.blood_type', read_only=True)
    
    class Meta:
        model = DonorNotification
        fields = '__all__'


class DonorResponseSerializer(serializers.ModelSerializer):
    donor_name = serializers.CharField(source='donor.full_name', read_only=True)
    
    class Meta:
        model = DonorResponse
        fields = '__all__'


class DonationHistorySerializer(serializers.ModelSerializer):
    donor_name = serializers.CharField(source='donor.full_name', read_only=True)
    hospital_name = serializers.CharField(source='hospital.hospital_name', read_only=True)
    
    class Meta:
        model = DonationHistory
        fields = '__all__'