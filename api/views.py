# api/views.py - COMPLETE VERSION WITH BLOOD REQUESTS

from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Q, Count
from datetime import datetime, timedelta

# Import models
from donors.models import DonorProfile, DonorNotification, DonationHistory
from hospitals.models import HospitalProfile, BloodRequest

# Import serializers
from .serializers import (
    DonorSerializer, 
    HospitalSerializer,
    BloodRequestSerializer,
    DonorNotificationSerializer,
    DonationHistorySerializer,
)


class DonorViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Donor management
    """
    permission_classes = [AllowAny]
    queryset = DonorProfile.objects.all()
    serializer_class = DonorSerializer

    def get_queryset(self):
        queryset = DonorProfile.objects.all()
        
        # Filter by blood type if provided
        blood_type = self.request.query_params.get('blood_type', None)
        if blood_type:
            queryset = queryset.filter(blood_type=blood_type)
        
        # Filter by availability
        is_available = self.request.query_params.get('is_available', None)
        if is_available is not None:
            queryset = queryset.filter(is_available=is_available.lower() == 'true')
        
        return queryset.select_related('user')

    @action(detail=True, methods=['get'])
    def donation_history(self, request, pk=None):
        """Get donation history for a specific donor"""
        donor = self.get_object()
        history = DonationHistory.objects.filter(donor=donor)
        serializer = DonationHistorySerializer(history, many=True)
        return Response(serializer.data)


class HospitalViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Hospital management
    """
    permission_classes = [AllowAny]
    queryset = HospitalProfile.objects.all()
    serializer_class = HospitalSerializer

    def get_queryset(self):
        return HospitalProfile.objects.all().select_related('user')

    @action(detail=True, methods=['get'])
    def blood_requests(self, request, pk=None):
        """Get all blood requests for a specific hospital"""
        hospital = self.get_object()
        requests = BloodRequest.objects.filter(hospital=hospital)
        serializer = BloodRequestSerializer(requests, many=True)
        return Response(serializer.data)


class BloodRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Blood Request management
    """
    permission_classes = [AllowAny]
    queryset = BloodRequest.objects.all()
    serializer_class = BloodRequestSerializer

    def get_queryset(self):
        queryset = BloodRequest.objects.all().select_related('hospital')
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by urgency
        urgency = self.request.query_params.get('urgency', None)
        if urgency:
            queryset = queryset.filter(urgency_level=urgency)
        
        # Filter by blood type
        blood_type = self.request.query_params.get('blood_type', None)
        if blood_type:
            queryset = queryset.filter(blood_type=blood_type)
        
        return queryset.order_by('-created_at')

    @action(detail=True, methods=['get'])
    def matched_donors(self, request, pk=None):
        """
        Get matched donors for a specific blood request
        Returns donors ordered by priority
        """
        blood_request = self.get_object()
        
        # Get all notifications for this request, ordered by priority
        notifications = DonorNotification.objects.filter(
            blood_request=blood_request
        ).select_related('donor').order_by('priority_order')
        
        matched_donors = []
        for notification in notifications:
            donor = notification.donor
            matched_donors.append({
                'donor': {
                    'id': donor.id,
                    'full_name': donor.full_name,
                    'blood_type': donor.blood_type,
                    'phone': donor.phone,
                    'location': donor.address,  # Using address as location
                    'email': donor.user.email if hasattr(donor, 'user') else None,
                },
                'match_score': notification.match_score or 0,
                'distance': notification.distance,
                'priority_order': notification.priority_order,
                'status': notification.status,
                'is_notified': notification.is_notified,
                'notified_at': notification.notified_at,
            })
        
        return Response({
            'blood_request_id': blood_request.id,
            'blood_type': blood_request.blood_type,
            'matched_donors': matched_donors,
            'total_matches': len(matched_donors),
        })


# Dashboard Statistics View
@api_view(['GET'])
@permission_classes([AllowAny])
def dashboard_stats(request):
    """
    Get dashboard statistics
    """
    total_donors = DonorProfile.objects.count()
    total_hospitals = HospitalProfile.objects.count()
    
    # Blood request stats
    total_requests = BloodRequest.objects.count()
    active_requests = BloodRequest.objects.filter(status='pending').count()
    fulfilled_requests = BloodRequest.objects.filter(status='fulfilled').count()
    
    # Blood type distribution
    blood_type_dist = {}
    for blood_type in ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-']:
        count = DonorProfile.objects.filter(blood_type=blood_type).count()
        blood_type_dist[blood_type] = count
    
    # Recent activity
    recent_requests = BloodRequest.objects.order_by('-created_at')[:10]
    recent_donations = DonationHistory.objects.order_by('-date_donated')[:10]
    
    return Response({
        'total_donors': total_donors,
        'total_hospitals': total_hospitals,
        'total_requests': total_requests,
        'active_requests': active_requests,
        'fulfilled_requests': fulfilled_requests,
        'completed_requests': fulfilled_requests,  # Alias
        'blood_type_distribution': blood_type_dist,
        'recent_requests_count': recent_requests.count(),
        'recent_donations_count': recent_donations.count(),
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def donor_leaderboard(request):
    """
    Get top donors by donation count
    """
    top_donors = DonorProfile.objects.filter(
        donation_count__gt=0
    ).order_by('-donation_count')[:20]
    
    serializer = DonorSerializer(top_donors, many=True)
    return Response(serializer.data)