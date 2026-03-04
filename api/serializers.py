# api/serializers.py

from rest_framework import serializers
from donors.models import DonorProfile, DonorNotification, DonationHistory
from hospitals.models import HospitalProfile, BloodRequest


class DonorSerializer(serializers.ModelSerializer):
    email    = serializers.EmailField(source='user.email', read_only=True)
    location = serializers.CharField(source='address', read_only=True)
    points   = serializers.IntegerField(read_only=True)

    class Meta:
        model  = DonorProfile
        fields = [
            'id',
            'full_name',
            'age',
            'phone',
            'blood_type',
            'address',
            'location',
            'latitude',
            'longitude',
            'donation_count',
            'last_donation_date',
            'is_available',
            'points',
            'email',
            'created_at',
            'updated_at',
        ]

    def to_representation(self, instance):
        """Safely handle missing fields without crashing"""
        ret = {}
        for field_name in self.Meta.fields:
            try:
                ret[field_name] = super().to_representation(instance).get(field_name)
            except Exception:
                ret[field_name] = None
        return ret


class HospitalSerializer(serializers.ModelSerializer):
    email    = serializers.EmailField(source='user.email', read_only=True)
    name     = serializers.CharField(source='hospital_name', read_only=True)
    location = serializers.CharField(source='address', read_only=True)

    class Meta:
        model  = HospitalProfile
        fields = [
            'id',
            'hospital_name',
            'name',
            'phone',
            'address',
            'location',
            'latitude',
            'longitude',
            'license_number',
            'is_verified',
            'email',
            'created_at',
            'updated_at',
        ]

    def to_representation(self, instance):
        ret = {}
        for field_name in self.Meta.fields:
            try:
                ret[field_name] = super().to_representation(instance).get(field_name)
            except Exception:
                ret[field_name] = None
        return ret


class BloodRequestSerializer(serializers.ModelSerializer):
    hospital_name     = serializers.CharField(source='hospital.hospital_name', read_only=True)
    hospital_location = serializers.CharField(source='hospital.address', read_only=True)
    hospital_phone    = serializers.CharField(source='hospital.phone', read_only=True)
    urgency           = serializers.CharField(source='urgency_level', read_only=True)

    class Meta:
        model  = BloodRequest
        fields = [
            'id',
            'hospital',
            'hospital_name',
            'hospital_location',
            'hospital_phone',
            'blood_type',
            'units_needed',
            'urgency_level',
            'urgency',
            'patient_name',
            'patient_age',
            'condition',
            'notes',
            'status',
            'created_at',
            'updated_at',
            'required_by',
        ]

    def to_representation(self, instance):
        ret = {}
        for field_name in self.Meta.fields:
            try:
                ret[field_name] = super().to_representation(instance).get(field_name)
            except Exception:
                ret[field_name] = None
        return ret


class DonorNotificationSerializer(serializers.ModelSerializer):
    donor_name       = serializers.CharField(source='donor.full_name',             read_only=True)
    donor_blood_type = serializers.CharField(source='donor.blood_type',            read_only=True)
    donor_phone      = serializers.CharField(source='donor.phone',                 read_only=True)
    donor_location   = serializers.CharField(source='donor.address',               read_only=True)
    request_blood_type = serializers.CharField(source='blood_request.blood_type',  read_only=True)
    request_urgency  = serializers.CharField(source='blood_request.urgency_level', read_only=True)
    hospital_name    = serializers.CharField(source='blood_request.hospital.hospital_name', read_only=True)

    class Meta:
        model  = DonorNotification
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
            'priority_order',
            'status',
            'is_notified',
            'notified_at',
        ]

    def to_representation(self, instance):
        ret = {}
        for field_name in self.Meta.fields:
            try:
                ret[field_name] = super().to_representation(instance).get(field_name)
            except Exception:
                ret[field_name] = None
        return ret


class DonationHistorySerializer(serializers.ModelSerializer):
    donor_name   = serializers.SerializerMethodField()
    hospital_name = serializers.SerializerMethodField()

    class Meta:
        model  = DonationHistory
        fields = [
            'id',
            'donor',
            'donor_name',
            'blood_request',
            'donor_name',
            'hospital_name',
            'date_donated',
            'is_verified',
            'created_at',
        ]

    def get_donor_name(self, obj):
        try:
            return obj.donor.full_name
        except Exception:
            return None

    def get_hospital_name(self, obj):
        try:
            return obj.blood_request.hospital.hospital_name
        except Exception:
            return None

    def to_representation(self, instance):
        ret = {}
        for field_name in self.Meta.fields:
            try:
                ret[field_name] = super().to_representation(instance).get(field_name)
            except Exception:
                ret[field_name] = None
        return ret