# donors/tasks.py (NEW FILE - Create this)
"""
Celery tasks for automatic donor notifications
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from donors.models import DonorNotification
from hospitals.models import BloodRequest
from django.core.mail import send_mail
from django.conf import settings


@shared_task
def notify_first_donor(blood_request_id):
    """
    Automatically notify the first donor when a blood request is created
    Called immediately after BloodRequest is saved
    """
    try:
        blood_request = BloodRequest.objects.get(id=blood_request_id)
        
        # Check if already accepted
        if blood_request.donor_notifications.filter(status='accepted').exists():
            return f"Request {blood_request_id} already accepted"
        
        # Get first donor (priority #1)
        first_notification = blood_request.donor_notifications.filter(
            status='pending',
            is_notified=False
        ).order_by('priority_order').first()
        
        if not first_notification:
            return f"No donors available for request {blood_request_id}"
        
        # Activate notification
        first_notification.status = 'notified'
        first_notification.is_notified = True
        first_notification.notified_at = timezone.now()
        first_notification.save()
        
        # Send email to donor
        send_donor_email(first_notification)
        
        # Schedule timeout check (30 minutes)
        check_donor_response.apply_async(
            args=[first_notification.id],
            countdown=30 * 60  # 30 minutes in seconds
        )
        
        return f"✅ Notified {first_notification.donor.full_name} (Priority #{first_notification.priority_order})"
        
    except BloodRequest.DoesNotExist:
        return f"Blood request {blood_request_id} not found"
    except Exception as e:
        return f"Error: {str(e)}"


@shared_task
def check_donor_response(notification_id):
    """
    Check if donor responded within 30 minutes
    If not, automatically notify next donor
    """
    try:
        notification = DonorNotification.objects.get(id=notification_id)
        
        # If donor already responded, do nothing
        if notification.status in ['accepted', 'rejected']:
            return f"Donor already responded: {notification.status}"
        
        # If still notified (no response after 30 mins), move to next donor
        if notification.status == 'notified':
            blood_request = notification.blood_request
            
            # Mark this notification as timed out/cancelled
            notification.status = 'cancelled'
            notification.response_notes = 'No response within 30 minutes - auto-cancelled'
            notification.save()
            
            # Notify next donor
            next_notification = blood_request.donor_notifications.filter(
                status='pending',
                is_notified=False
            ).order_by('priority_order').first()
            
            if next_notification:
                # Activate next donor
                next_notification.status = 'notified'
                next_notification.is_notified = True
                next_notification.notified_at = timezone.now()
                next_notification.save()
                
                # Send email
                send_donor_email(next_notification)
                
                # Schedule next timeout check
                check_donor_response.apply_async(
                    args=[next_notification.id],
                    countdown=30 * 60
                )
                
                # Notify admin
                notify_admin_timeout(notification, next_notification)
                
                return f"⏰ Timeout! Notified next donor: {next_notification.donor.full_name}"
            else:
                # No more donors
                notify_admin_no_donors(blood_request)
                return f"⚠️ No more donors available for request {blood_request.id}"
        
        return f"Notification {notification_id} status: {notification.status}"
        
    except DonorNotification.DoesNotExist:
        return f"Notification {notification_id} not found"
    except Exception as e:
        return f"Error: {str(e)}"


def send_donor_email(notification):
    """Send email notification to donor"""
    donor = notification.donor
    blood_request = notification.blood_request
    
    message = f"""
🔴 URGENT BLOOD NEEDED - IMMEDIATE RESPONSE REQUIRED

Hospital: {blood_request.hospital.hospital_name}
Patient: {blood_request.patient_name}
Blood Type: {blood_request.blood_type}
Units: {blood_request.units_needed}
Urgency: {blood_request.urgency_level.upper()}
Distance: {notification.distance:.2f}km from you

⏰ IMPORTANT: Please respond within 30 minutes
If you don't respond, the request will automatically go to the next donor.

Login to respond: {settings.SITE_URL}/donors/dashboard/

Match Score: {int(notification.match_score * 100)}%
You are Priority #{notification.priority_order}

Thank you for being a lifesaver!
LifeLink Nepal
    """.strip()
    
    if donor.user.email:
        try:
            send_mail(
                subject=f"🔴 URGENT: Blood Request - Respond in 30 mins",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[donor.user.email],
                fail_silently=False,
            )
            print(f"📧 Email sent to {donor.full_name}")
        except Exception as e:
            print(f"❌ Email failed: {e}")


def notify_admin_timeout(timed_out_notification, next_notification):
    """Notify admin when a donor times out"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    admins = User.objects.filter(is_superuser=True, is_active=True)
    blood_request = timed_out_notification.blood_request
    
    message = f"""
⏰ DONOR TIMEOUT - AUTO-NOTIFIED NEXT DONOR

Request ID: #{blood_request.id}
Hospital: {blood_request.hospital.hospital_name}

TIMED OUT:
Donor: {timed_out_notification.donor.full_name}
Priority: #{timed_out_notification.priority_order}
No response after 30 minutes

NOW NOTIFIED:
Donor: {next_notification.donor.full_name}
Priority: #{next_notification.priority_order}
Phone: {next_notification.donor.phone}

View: {settings.SITE_URL}/admin/hospitals/bloodrequest/{blood_request.id}/change/
    """.strip()
    
    admin_emails = [admin.email for admin in admins if admin.email]
    if admin_emails:
        send_mail(
            subject=f"⏰ Timeout - Next Donor Notified - Request #{blood_request.id}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=admin_emails,
            fail_silently=True,
        )


def notify_admin_no_donors(blood_request):
    """Notify admin when no more donors available"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    admins = User.objects.filter(is_superuser=True, is_active=True)
    
    message = f"""
⚠️ NO MORE DONORS AVAILABLE

Request ID: #{blood_request.id}
Hospital: {blood_request.hospital.hospital_name}
Patient: {blood_request.patient_name}
Blood Type: {blood_request.blood_type}

All eligible donors have been notified but none responded.

ACTION REQUIRED: Please contact hospital or find donors manually.

View: {settings.SITE_URL}/admin/hospitals/bloodrequest/{blood_request.id}/change/
    """.strip()
    
    admin_emails = [admin.email for admin in admins if admin.email]
    if admin_emails:
        send_mail(
            subject=f"⚠️ URGENT - No Donors Available - Request #{blood_request.id}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=admin_emails,
            fail_silently=True,
        )