from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Reminder


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ('title', 'remind_at', 'recurrence', 'active', 'status_display', 'created_at')
    list_filter = ('active', 'recurrence')
    search_fields = ('title', 'description')
    list_editable = ('active',)
    readonly_fields = ('created_at',)

    fieldsets = (
        (None, {'fields': ('title', 'description')}),
        ('Schedule', {'fields': ('remind_at', 'recurrence')}),
        ('Status', {'fields': ('active', 'created_at')}),
    )

    def status_display(self, obj):
        now = timezone.now()
        if not obj.active:
            return format_html('<span style="color:{}">{}</span>', '#6b7280', 'Inactive')
        if obj.remind_at < now:
            return format_html('<span style="color:{}">{}</span>', '#ef4444', 'Past due')
        if obj.is_upcoming_today:
            return format_html('<span style="color:{}"; font-weight:bold">{}</span>', '#10b981', 'Today')
        
        return format_html('<span style="color:{}">{}</span>', '#60a5fa', 'Upcoming')
    
    status_display.short_description = 'Status'
