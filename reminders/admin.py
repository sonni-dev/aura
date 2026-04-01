from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Reminder


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'frequency', 'channel', 'next_run_display', 'source_label_display',
        'next_run_display', 'source_link', 'is_urgent_display', 'is_active', 'is_complete',
    ]
    list_filter = ['frequency', 'channel', 'is_active', 'is_complete']
    search_fields = ['title', 'description']
    list_editable = ['is_active', 'is_complete']
    readonly_fields = ['created_at', 'updated_at', 'last_run', 'source_display', 'completed_at']
    ordering = ['is_complete', 'next_run',]


    fieldsets = [
        (None, {
            'fields': ['title', 'description', 'channel'],
        }),
        ('Schedule', {
            'fields': ['frequency', 'interval', 'start_date', 'next_run', 'last_run'],
        }),
        ('Completion', {
            'fields': ['is_complete', 'completed_at'],
            'description': (
                'Mark a reminder complete/dismissed here, or use the '
                '"Dismiss selected reminders" bulk action. '
                'Dismissing will also complete the linked source object where applicable.'
            ),
        }),
        ('Source — link to at most one', {
            'description': (
                'Connect this reminder to a source object. '
                'Item-level links (Goal Item, Routine Item) are preferred for '
                'granular reminders tied to a single step rather than the whole parent. '
                'Leave all blank for a standalone reminder.'
            ),

            'fields': ['task', 'routine_item', 'routine', 'goal_item', 'goal', 'habit', 'source_display'],
        }),
        ('State', {
            'fields': ['is_active',],
        }),
        ('Timestamps', {
            'classes': ['collapse',],
            'fields': ['created_at', 'updated_at'],
        }),
    ]

    # actions = ['deactivate_reminders', 'advance_next_run']
    actions = ['dismiss_reminders', 'reactivate_reminders']

    # ── List display helpers ──────────────────────────────────────────────

    @admin.display(description='Next Run')
    def next_run_display(self, obj):
        if not obj.next_run:
            return '—'
        if obj.is_complete:
            return format_html('<span style="{}">{}</span>', 'color:#6b7280;', 'dismissed')
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
    
    @admin.display(description='Source')
    def source_label_display(self, obj):
        label = obj.source_label
        colors = {
            'Task':         '#84cc16',
            'Goal Item':    '#a855f7',
            'Goal':         '#06b6d4',
            'Routine Item': '#f97316',
            'Routine':      '#f97316',
            'Habit':        '#ec4899',
            'Standalone':   '#6b7280',
        }
        color = colors.get(label, '#6b7280')
        src   = obj.source
        src_str = str(src) if src else '—'
        return format_html(
            '<span style="color:{}; font-size:11px;">● {}</span><br>'
            '<span style="color:#9ca3af; font-size:11px;">{}</span>',
            color, label, src_str,
        )

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
        if src is None:
            return 'Standalone (no source linked)'
        return f'{obj.source_label}: {src}'
    

    # ── Bulk actions ──────────────────────────────────────────────────────

    # @admin.action(description='Deactivate selected reminders')
    # def deactivate_reminders(self, request, queryset):
    #     queryset.update(is_active=False)
    #     self.message_user(request, f'{queryset.count()} reminder(s) deactivated.')
    

    # @admin.action(description='Advance next_run forward (fire and reschedule)')
    # def advance_next_run(self, request, queryset):
    #     for r in queryset:
    #         r.advance_next_run()
    #     self.message_user(request, f'{queryset.count()} reminder(s) rescheduled.')


    @admin.action(description='Dismiss selected reminders (mark complete)')
    def dismiss_reminders(self, request, queryset):
        count = 0
        for reminder in queryset.filter(is_complete=False):
            # sync-source=True so source objects are also marked complete
            reminder.dismiss(sync_source=True)
            count += 1
        self.message_user(request, f'{count} reminder(s) dismissed.')
    

    @admin.action(description='Re-activate selected reminders')
    def reactivate_reminders(self, request, queryset):
        updated = queryset.update(
            is_complete=False,
            completed_at=None,
            is_active=True,
        )
        self.message_user(request, f'{updated} reminder(s) re-activated.')


