# api/views.py - UPDATED WITH SESSION AUTHENTICATION
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from django.core.mail import send_mail
from django.conf import settings
from django.db import models

from donors.models import DonorProfile
from hospitals.models import HospitalProfile, BloodRequest
from donors.serializers import DonorSerializer
from hospitals.serializers import HospitalSerializer, BloodRequestSerializer


class DonorViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for viewing donors"""
    queryset = DonorProfile.objects.all().order_by('-created_at')
    serializer_class = DonorSerializer
    # Support both session (for admin panel) and JWT (for mobile/external)
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        blood_type = self.request.query_params.get('blood_type')
        if blood_type and blood_type != 'all':
            queryset = queryset.filter(blood_type=blood_type)
        return queryset


class HospitalViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for viewing hospitals"""
    queryset = HospitalProfile.objects.all().order_by('-created_at')
    serializer_class = HospitalSerializer
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]


class BloodRequestViewSet(viewsets.ModelViewSet):
    """API endpoint for managing blood requests"""
    queryset = BloodRequest.objects.all().order_by('-created_at')
    serializer_class = BloodRequestSerializer
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get('status')
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)
        return queryset
    
    @action(detail=True, methods=['post'])
    def notify_donors(self, request, pk=None):
        """Notify compatible donors about a blood request"""
        blood_request = self.get_object()
        
        # Get compatible blood types
        compatible_types = get_compatible_blood_types(blood_request.blood_type)
        
        # Get eligible donors (who can donate - 90 days since last donation)
        from datetime import date, timedelta
        eligible_date = date.today() - timedelta(days=90)
        
        eligible_donors = DonorProfile.objects.filter(
            blood_type__in=compatible_types,
            is_available=True
        ).filter(
            models.Q(last_donation_date__isnull=True) | 
            models.Q(last_donation_date__lte=eligible_date)
        )
        
        notified_count = 0
        errors = []
        
        # Notify each donor
        for donor in eligible_donors:
            try:
                send_donor_notification(donor, blood_request)
                notified_count += 1
            except Exception as e:
                errors.append(f"Error notifying {donor.id}: {str(e)}")
        
        # Update request status
        if notified_count > 0 and blood_request.status == 'pending':
            blood_request.status = 'matched'
            blood_request.save()
        
        return Response({
            'message': f'Successfully notified {notified_count} out of {eligible_donors.count()} donors',
            'notified_count': notified_count,
            'total_eligible': eligible_donors.count(),
            'errors': errors if errors else None
        }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def dashboard_stats(request):
    """Get dashboard statistics"""
    from datetime import date, timedelta
    
    # Get donors who can donate (haven't donated in 90 days)
    eligible_date = date.today() - timedelta(days=90)
    available_donors = DonorProfile.objects.filter(
        is_available=True
    ).filter(
        models.Q(last_donation_date__isnull=True) | 
        models.Q(last_donation_date__lte=eligible_date)
    ).count()
    
    return Response({
        'total_donors': DonorProfile.objects.count(),
        'available_donors': available_donors,
        'total_hospitals': HospitalProfile.objects.count(),
        'active_requests': BloodRequest.objects.filter(
            status__in=['pending', 'matched']
        ).count(),
        'completed_requests': BloodRequest.objects.filter(
            status='completed'
        ).count(),
    })


# Helper functions
def get_compatible_blood_types(blood_type):
    """Get compatible donor blood types"""
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


def send_donor_notification(donor, blood_request):
    """Send email notification to donor"""
    
    # Get donor's email
    donor_email = donor.user.email if donor.user else None
    
    if not donor_email:
        raise Exception(f"No email found for donor {donor.full_name}")
    
    # Get hospital details
    hospital_name = getattr(blood_request.hospital, 'hospital_name', 'Hospital')
    hospital_phone = getattr(blood_request.hospital, 'phone', 'N/A')
    hospital_address = getattr(blood_request.hospital, 'address', 'N/A')
    
    subject = f'🩸 Urgent: {blood_request.blood_type} Blood Needed - LifeLink Nepal'
    
    message = f"""
Dear {donor.full_name},

We urgently need your help!

Blood Type Needed: {blood_request.blood_type}
Units Required: {blood_request.units_needed}
Hospital: {hospital_name}
Urgency Level: {blood_request.urgency.upper()}
Patient: {getattr(blood_request, 'patient_name', 'N/A')}
Reason: {getattr(blood_request, 'reason', 'Emergency')}

Contact Details:
Phone: {hospital_phone}
Address: {hospital_address}

Please contact the hospital immediately if you can donate.
Your donation can save a life!

Thank you for being a lifesaver.

Best regards,
LifeLink Nepal Team
    """
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [donor_email],
        fail_silently=False,
    )