# hospitals/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import BloodRequest, HospitalProfile
from django.core.mail import send_mail
from django.conf import settings


@admin.register(BloodRequest)
class BloodRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 
        'hospital_name', 
        'patient_name', 
        'blood_type', 
        'urgency_level', 
        'status',
        'donor_count',
        'current_donor',
        'action_buttons'
    ]
    list_filter = ['status', 'urgency_level', 'blood_type', 'created_at']
    search_fields = ['patient_name', 'hospital__hospital_name', 'condition']
    readonly_fields = ['created_at', 'updated_at', 'donor_list_display']
    
    fieldsets = (
        ('Request Information', {
            'fields': ('hospital', 'patient_name', 'patient_age', 'blood_type', 
                      'units_needed', 'urgency_level', 'condition', 'notes', 'status')
        }),
        ('Donor Management', {
            'fields': ('donor_list_display',),
            'description': 'List of matched donors sorted by distance (nearest first)'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def hospital_name(self, obj):
        return obj.hospital.hospital_name
    hospital_name.short_description = 'Hospital'
    
    def donor_count(self, obj):
        total = obj.donor_notifications.count()
        pending = obj.donor_notifications.filter(status='pending').count()
        notified = obj.donor_notifications.filter(status='notified').count()
        accepted = obj.donor_notifications.filter(status='accepted').count()
        
        return format_html(
            '<span style="color: blue;">Total: {}</span> | '
            '<span style="color: orange;">Pending: {}</span> | '
            '<span style="color: purple;">Notified: {}</span> | '
            '<span style="color: green;">Accepted: {}</span>',
            total, pending, notified, accepted
        )
    donor_count.short_description = 'Donors'
    
    def current_donor(self, obj):
        """Show currently notified donor or accepted donor"""
        # Check if someone accepted
        accepted = obj.donor_notifications.filter(status='accepted').first()
        if accepted:
            return format_html(
                '<strong style="color: green;">✅ ACCEPTED</strong><br>'
                'Username: {}<br>Blood Type: {}<br>Distance: {}km',
                accepted.donor.user.username,
                accepted.donor.blood_type,
                round(accepted.distance, 2) if accepted.distance else 'N/A'
            )
        
        # Check who's currently notified
        notified = obj.donor_notifications.filter(status='notified', is_notified=True).first()
        if notified:
            return format_html(
                '<strong style="color: orange;">⏳ WAITING</strong><br>'
                '{} (Priority #{})<br>Notified: {}',
                notified.donor.full_name,
                notified.priority_order,
                notified.notified_at.strftime('%Y-%m-%d %H:%M') if notified.notified_at else 'N/A'
            )
        
        return format_html('{}', '<span style="color: gray;">No donor notified yet</span>')
    current_donor.short_description = 'Current Status'
    
    def action_buttons(self, obj):
        """Action buttons for notifying donors"""
        if obj.status != 'pending':
            return format_html('<span style="color: gray;">Request {}</span>', obj.status)
        
        # Check if accepted
        if obj.donor_notifications.filter(status='accepted').exists():
            return format_html('{}', '<span style="color: green;">✅ Donor Accepted</span>')
        
        # Check if someone is currently waiting
        waiting = obj.donor_notifications.filter(status='notified', is_notified=True).exists()
        if waiting:
            return format_html(
                '<span style="color: orange;">⏳ Waiting for donor response...</span>'
            )
        
        # Show "Notify Next Donor" button
        next_donor = obj.donor_notifications.filter(
            is_notified=False, 
            status='pending'
        ).order_by('priority_order').first()
        
        if next_donor:
            return format_html(
                '<a class="button" href="/admin/hospitals/bloodrequest/{}/notify-next/" '
                'style="background-color: #417690; color: white; padding: 5px 10px; '
                'text-decoration: none; border-radius: 3px;">'
                '🔔 Notify Next Donor ({})</a>',
                obj.id,
                next_donor.donor.full_name
            )
        
        return format_html('{}', '<span style="color: red;">No more donors available</span>')
    action_buttons.short_description = 'Actions'
    
    def donor_list_display(self, obj):
        """Display full donor list with all details (only visible in admin)"""
        notifications = obj.donor_notifications.all().order_by('priority_order')
        
        if not notifications:
            return format_html('{}', '<p style="color: red;">No eligible donors found</p>')
        
        html = '<table style="width: 100%; border-collapse: collapse;">'
        html += '''
        <thead>
            <tr style="background-color: #f5f5f5;">
                <th style="border: 1px solid #ddd; padding: 8px;">Priority</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Full Name</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Username</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Phone</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Blood Type</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Distance</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Match Score</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Status</th>
            </tr>
        </thead>
        <tbody>
        '''
        
        for notif in notifications[:20]:  # Show top 20
            donor = notif.donor
            
            # Color code status
            status_colors = {
                'pending': 'gray',
                'notified': 'orange',
                'accepted': 'green',
                'rejected': 'red',
                'cancelled': 'gray'
            }
            status_color = status_colors.get(notif.status, 'black')
            
            html += f'''
            <tr>
                <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">
                    <strong>#{notif.priority_order}</strong>
                </td>
                <td style="border: 1px solid #ddd; padding: 8px;">{donor.full_name}</td>
                <td style="border: 1px solid #ddd; padding: 8px;">{donor.user.username}</td>
                <td style="border: 1px solid #ddd; padding: 8px;">{donor.phone}</td>
                <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">
                    <strong>{donor.blood_type}</strong>
                </td>
                <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">
                    {round(notif.distance, 2) if notif.distance else 'N/A'} km
                </td>
                <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">
                    {int(notif.match_score * 100) if notif.match_score else 0}%
                </td>
                <td style="border: 1px solid #ddd; padding: 8px; color: {status_color};">
                    <strong>{notif.status.upper()}</strong>
                </td>
            </tr>
            '''
        
        html += '</tbody></table>'
        return format_html('{}', html)
    donor_list_display.short_description = 'Matched Donors (Full Details - Admin Only)'
    
    def get_urls(self):
        """Add custom URL for notifying next donor"""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:request_id>/notify-next/',
                self.admin_site.admin_view(self.notify_next_donor_view),
                name='bloodrequest_notify_next',
            ),
        ]
        return custom_urls + urls
    
    def notify_next_donor_view(self, request, request_id):
        """Handle notifying the next donor"""
        from django.shortcuts import redirect
        from django.contrib import messages
        
        blood_request = BloodRequest.objects.get(id=request_id)
        
        # Check if already accepted
        if blood_request.donor_notifications.filter(status='accepted').exists():
            messages.warning(request, "A donor has already accepted this request.")
            return redirect('admin:hospitals_bloodrequest_change', request_id)
        
        # Check if someone is waiting
        if blood_request.donor_notifications.filter(status='notified', is_notified=True).exists():
            messages.warning(request, "A donor is currently reviewing this request. Please wait.")
            return redirect('admin:hospitals_bloodrequest_change', request_id)
        
        # Get next donor
        next_notification = blood_request.donor_notifications.filter(
            is_notified=False,
            status='pending'
        ).order_by('priority_order').first()
        
        if not next_notification:
            messages.error(request, "No more donors available to notify.")
            return redirect('admin:hospitals_bloodrequest_change', request_id)
        
        # Notify donor
        next_notification.is_notified = True
        next_notification.status = 'notified'
        next_notification.notified_at = timezone.now()
        next_notification.save()
        
        # Send notification
        self.send_donor_notification(next_notification.donor, blood_request, next_notification)
        
        messages.success(
            request,
            f"✅ Notification sent to {next_notification.donor.full_name} "
            f"(Priority #{next_notification.priority_order})"
        )
        
        return redirect('admin:hospitals_bloodrequest_change', request_id)
    
    def send_donor_notification(self, donor, blood_request, notification):
        """Send email/SMS to donor"""
        message = f"""
🔴 URGENT BLOOD NEEDED

Hospital: {blood_request.hospital.hospital_name}
Patient: {blood_request.patient_name}
Blood Type: {blood_request.blood_type}
Units: {blood_request.units_needed}
Urgency: {blood_request.urgency_level.upper()}
Distance: {notification.distance:.2f}km

You are a {int(notification.match_score * 100)}% match!

Please login to LifeLink Nepal to respond.
        """.strip()
        
        # Send email
        if donor.user.email:
            send_mail(
                subject=f"🔴 URGENT: Blood Request - {blood_request.blood_type}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[donor.user.email],
                fail_silently=True,
            )
        
        print(f"📧 Email sent to {donor.full_name} ({donor.user.email})")
        print(f"📱 SMS to {donor.phone}: {message}")


@admin.register(HospitalProfile)
class HospitalProfileAdmin(admin.ModelAdmin):
    list_display = ['hospital_name', 'phone', 'address', 'is_verified', 'total_requests']
    list_filter = ['is_verified', 'created_at']
    search_fields = ['hospital_name', 'phone', 'address']
    
    def total_requests(self, obj):
        total = obj.blood_requests.count()
        pending = obj.blood_requests.filter(status='pending').count()
        fulfilled = obj.blood_requests.filter(status='fulfilled').count()
        
        return format_html(
            'Total: {} | Pending: {} | Fulfilled: {}',
            total, pending, fulfilled
        )
    total_requests.short_description = 'Requests'