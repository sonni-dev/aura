from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Reminder


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'frequency', 'channel', 'next_run_display',
        'source_link', 'is_urgent_display', 'is_active',
    ]
    list_filter = ['frequency', 'channel', 'is_active']
    search_fields = ['title', 'description']
    list_editable = ['is_active', ]
    readonly_fields = ['created_at', 'updated_at', 'last_run', 'source_display']
    ordering = ['next_run',]


    fieldsets = [
        (None, {
            'fields': ['title', 'description', 'channel'],
        }),
        ('Schedule', {
            'fields': ['frequency', 'interval', 'start_date', 'next_run', 'last_run'],
        }),
        ('Source (link to at most one)', {
            'description': 'Connect this reminder to a task, routine, goal, or habit. Leave all blank for standalone reminder.',
            'fields': ['task', 'routine', 'goal', 'habit'],
        }),
        ('State', {
            'fields': ['is_active',],
        }),
        ('Timestamps', {
            'classes': ['collapse',],
            'fields': ['created_at', 'updated_at'],
        }),
    ]

    actions = ['deactivate_reminders', 'advance_next_run']

    @admin.display(description='Next Run')
    def next_run_display(self, obj):
        if not obj.next_run:
            return format_html('<span style="{}">—</span>', 'color:#6b7280;')
        now = timezone.now()
        if obj.next_run < now:
            return format_html(
                '<span style="color:#ef4444; font-weight:600;">OVERDUE — {}</span>',
                obj.next_run.strftime('%b %-d, %-I:%M %p')
            )
        delta = obj.next_run - now
        hours = delta.total_seconds() / 3600
        if hours < 1:
            color = '#f59e0b'
        elif hours < 24:
            color = '#10b981'
        else:
            color = '#6b7280'
        return format_html(
            '<span style="color:{};">{}</span>',
            color, obj.next_run.strftime('%b %-d, %-I:%M %p')
        )
    
    @admin.display(description='Urgent', boolean=True)
    def is_urgent_display(self, obj):
        return obj.is_urgent
    

    @admin.display(description='Linked To')
    def source_link(self, obj):
        src = obj.source
        if not src:
            return format_html('<span style="{}">Standalone</span>', 'color:#6b7280;')
        if obj.task:
            label = 'Task'
            color = '#3b82f6'
        elif obj.routine:
            label = 'Routine'
            color = '#8b5cf6'
        elif obj.goal:
            label = 'Goal'
            color = '#10b981'
        else:
            label = 'Habit'
            color = '#f59e0b'
        return format_html(
            '<span style="color:{};font-size:11px;font-weight:600;">{}</span> {}',
            color, label, str(src)[:30]
        )
    

    # Read-Only computed field for the detail page
    @admin.display(description='Source Object')
    def source_display(self, obj):
        src = obj.source
        return str(src) if src else '—'
    

    @admin.action(description='Deactivate selected reminders')
    def deactivate_reminders(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'{queryset.count()} reminder(s) deactivated.')
    

    @admin.action(description='Advance next_run forward (fire and reschedule)')
    def advance_next_run(self, request, queryset):
        for r in queryset:
            r.advance_next_run()
        self.message_user(request, f'{queryset.count()} reminder(s) rescheduled.')


