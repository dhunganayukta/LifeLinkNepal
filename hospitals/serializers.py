# hospitals/serializers.py
from rest_framework import serializers
from .models import HospitalProfile, BloodRequest
from donors.models import DonorProfile


class HospitalSerializer(serializers.ModelSerializer):
    email = serializers.SerializerMethodField()
    
    class Meta:
        model = HospitalProfile
        fields = '__all__'
    
    def get_email(self, obj):
        return obj.user.email if hasattr(obj, 'user') and obj.user else "N/A"


class BloodRequestSerializer(serializers.ModelSerializer):
    hospital_name = serializers.SerializerMethodField()
    contact_number = serializers.SerializerMethodField()
    eligible_donors_count = serializers.SerializerMethodField()
    
    class Meta:
        model = BloodRequest
        fields = '__all__'
    
    def get_hospital_name(self, obj):
        if hasattr(obj, 'hospital'):
            return getattr(obj.hospital, 'hospital_name', 'Unknown Hospital')
        return 'Unknown Hospital'
    
    def get_contact_number(self, obj):
        if hasattr(obj, 'hospital'):
            return getattr(obj.hospital, 'phone', 'N/A')
        return 'N/A'
    
    def get_eligible_donors_count(self, obj):
        compatible_types = self.get_compatible_blood_types(obj.blood_type)
        return DonorProfile.objects.filter(
            blood_type__in=compatible_types,
            is_available=True
        ).count()
    
    def get_compatible_blood_types(self, blood_type):
        """Blood type compatibility chart"""
        compatibility = {
            'A+': ['A+', 'A-', 'O+', 'O-'],
            'A-': ['A-', 'O-'],
            'B+': ['B+', 'B-', 'O+', 'O-'],
            'B-': ['B-', 'O-'],
            'AB+': ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],
            'AB-': ['A-', 'B-', 'AB-', 'O-'],
            'O+': ['O+', 'O-'],
            'O-': ['O-'],
        }
        return compatibility.get(blood_type, [])