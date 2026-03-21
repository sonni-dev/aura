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
            return format_html('<span style="color:#6b7280">Inactive</span>')
        if obj.remind_at < now:
            return format_html('<span style="color:#ef4444">Past due</span>')
        if obj.is_upcoming_today:
            return format_html('<span style="color:#10b981; font-weight:bold">Today</span>')
        return format_html('<span style="color:#60a5fa">Upcoming</span>')
    status_display.short_description = 'Status'
