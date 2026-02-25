from django.contrib import admin
from django.utils import timezone
from .models import DonorProfile, DonorNotification, DonorResponse, DonationHistory

POINTS_PER_DONATION = 50


@admin.register(DonorProfile)
class DonorProfileAdmin(admin.ModelAdmin):
    list_display   = ['full_name', 'blood_type', 'donation_count', 'points', 'is_available', 'can_donate_display']
    list_filter    = ['blood_type', 'is_available']
    search_fields  = ['full_name', 'user__username', 'phone']
    ordering       = ['-points']
    readonly_fields = ['donation_count', 'last_donation_date', 'created_at', 'updated_at']

    fieldsets = (
        ('Personal Info', {
            'fields': ('user', 'full_name', 'age', 'phone', 'blood_type', 'address')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude')
        }),
        ('Donation Stats', {
            'fields': ('donation_count', 'points', 'last_donation_date', 'is_available')
        }),
        ('Health', {
            'fields': ('weight', 'medical_conditions'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(boolean=True, description='Can Donate Now')
    def can_donate_display(self, obj):
        return obj.can_donate

    # Admin action: manually award points (e.g. for offline donation)
    actions = ['award_points_manually']

    @admin.action(description='Award 50 points to selected donors')
    def award_points_manually(self, request, queryset):
        updated = 0
        for donor in queryset:
            donor.points += POINTS_PER_DONATION
            donor.save(update_fields=['points'])
            updated += 1
        self.message_user(request, f'Awarded {POINTS_PER_DONATION} points to {updated} donor(s).')


@admin.register(DonorNotification)
class DonorNotificationAdmin(admin.ModelAdmin):
    list_display  = ['donor', 'blood_request', 'status', 'priority_order', 'is_notified', 'notified_at', 'responded_at']
    list_filter   = ['status', 'is_notified', 'is_read']
    search_fields = ['donor__full_name', 'blood_request__hospital__hospital_name']
    ordering      = ['priority_order', '-sent_at']
    readonly_fields = ['sent_at', 'notified_at', 'responded_at']

    # Admin action: manually notify next donor
    actions = ['notify_selected_donors']

    @admin.action(description='Mark selected donors as Notified (send notification)')
    def notify_selected_donors(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='notified',
            is_notified=True,
            notified_at=timezone.now(),
        )
        self.message_user(request, f'{updated} donor(s) marked as notified.')


@admin.register(DonorResponse)
class DonorResponseAdmin(admin.ModelAdmin):
    list_display  = ['donor', 'blood_request', 'status', 'responded_at']
    list_filter   = ['status']
    search_fields = ['donor__full_name']
    ordering      = ['-responded_at']


@admin.register(DonationHistory)
class DonationHistoryAdmin(admin.ModelAdmin):
    list_display  = ['donor', 'hospital', 'date_donated', 'units_donated', 'points_column']
    list_filter   = ['date_donated']
    search_fields = ['donor__full_name', 'hospital__hospital_name']
    ordering      = ['-date_donated']
    readonly_fields = ['created_at']

    @admin.display(description='Points Awarded')
    def points_column(self, obj):
        return f'+{POINTS_PER_DONATION}'