# api/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from datetime import date

from donors.models import DonorProfile, DonorNotification, DonationHistory
from hospitals.models import HospitalProfile, BloodRequest

from .serializers import (
    DonorSerializer,
    HospitalSerializer,
    BloodRequestSerializer,
    DonorNotificationSerializer,
    DonationHistorySerializer,
)


class DonorViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    serializer_class   = DonorSerializer

    def get_queryset(self):
        queryset = DonorProfile.objects.all().select_related('user')
        blood_type   = self.request.query_params.get('blood_type')
        is_available = self.request.query_params.get('is_available')
        if blood_type:
            queryset = queryset.filter(blood_type=blood_type)
        if is_available is not None:
            queryset = queryset.filter(is_available=is_available.lower() == 'true')
        return queryset

    @action(detail=True, methods=['get'])
    def donation_history(self, request, pk=None):
        donor   = self.get_object()
        history = DonationHistory.objects.filter(donor=donor)
        return Response(DonationHistorySerializer(history, many=True).data)


class HospitalViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    serializer_class   = HospitalSerializer

    def get_queryset(self):
        return HospitalProfile.objects.all().select_related('user')

    @action(detail=True, methods=['get'])
    def blood_requests(self, request, pk=None):
        hospital = self.get_object()
        requests = BloodRequest.objects.filter(hospital=hospital)
        return Response(BloodRequestSerializer(requests, many=True).data)


class BloodRequestViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    serializer_class   = BloodRequestSerializer

    def get_queryset(self):
        queryset = BloodRequest.objects.all().select_related('hospital')
        status_filter = self.request.query_params.get('status')
        urgency       = self.request.query_params.get('urgency')
        blood_type    = self.request.query_params.get('blood_type')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if urgency:
            queryset = queryset.filter(urgency_level=urgency)
        if blood_type:
            queryset = queryset.filter(blood_type=blood_type)
        return queryset.order_by('-created_at')

    @action(detail=True, methods=['get'])
    def matched_donors(self, request, pk=None):
        blood_request = self.get_object()
        notifications = DonorNotification.objects.filter(
            blood_request=blood_request
        ).select_related('donor', 'donor__user').order_by('priority_order')

        matched_donors = []
        for n in notifications:
            donor     = n.donor
            raw_score = n.match_score or 0
            # stored as 0-1 float → display as 0-100%
            score_pct = round(raw_score * 100, 1) if raw_score <= 1 else round(raw_score, 1)

            matched_donors.append({
                'donor': {
                    'id':         donor.id,
                    'full_name':  donor.full_name or 'Unknown',
                    'blood_type': donor.blood_type or 'N/A',
                    'phone':      getattr(donor, 'phone', None) or 'N/A',
                    'location':   getattr(donor, 'address', None) or 'N/A',
                    'email':      donor.user.email if hasattr(donor, 'user') else None,
                },
                'match_score':    score_pct,
                'distance':       round(n.distance, 2) if n.distance else None,
                'priority_order': n.priority_order,
                'status':         n.status,
                'is_notified':    n.is_notified,
                'notified_at':    n.notified_at,
            })

        return Response({
            'blood_request_id': blood_request.id,
            'blood_type':       blood_request.blood_type,
            'matched_donors':   matched_donors,
            'total_matches':    len(matched_donors),
        })


@api_view(['GET'])
@permission_classes([AllowAny])
def dashboard_stats(request):
    fulfilled = BloodRequest.objects.filter(status='fulfilled').count()
    return Response({
        'total_donors':            DonorProfile.objects.count(),
        'total_hospitals':         HospitalProfile.objects.count(),
        'total_requests':          BloodRequest.objects.count(),
        'active_requests':         BloodRequest.objects.filter(status='pending').count(),
        'fulfilled_requests':      fulfilled,
        'completed_requests':      fulfilled,
        'critical_requests':       BloodRequest.objects.filter(
                                       status__in=['pending','accepted','donor_confirmed'],
                                       urgency_level='critical').count(),
        'blood_type_distribution': {
            bt: DonorProfile.objects.filter(blood_type=bt).count()
            for bt in ['A+','A-','B+','B-','O+','O-','AB+','AB-']
        },
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def donor_leaderboard(request):
    top_donors = DonorProfile.objects.filter(
        donation_count__gt=0
    ).order_by('-donation_count', '-points')[:20]
    return Response(DonorSerializer(top_donors, many=True).data)