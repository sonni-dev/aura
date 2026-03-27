from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'status_badge', 'priority_badge', 'category',
        'energy_type', 'where_task', 'due_date', 'overdue_flag',
        'is_active', 'is_complete',
    ]
    list_filter = [
        'status', 'priority', 'category', 'energy_type', 'where_task', 'is_active', 'is_complete'
    ]
    search_fields = ('name', 'description')
    list_editable = ('is_active',)
    readonly_fields = ('is_active', 'created_at', 'updated_at')
    date_hierarchy = 'due_date'
    ordering = ['is_complete', 'due_date', '-priority']

    fieldsets = [
        (None, {
            'fields': ['name', 'description'],
        }),
        ('Classification', {
            'fields': ['status', 'priority', 'category', 'energy_type', 'where_task'],
        }),
        ('Schedule', {
            'fields': ['due_date',],
        }),
        ('State', {
            'fields': ['is_active', 'is_complete', 'completed_at'],
        }),
        ('Timestamps', {
            'classes': ['collapse',],
            'fields': ['created_at', 'updated_at'],
        }),
    ]

    actions = ['mark_complete', 'mark_in_progress', 'mark_stalled']

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {
            'todo':        ('#6b7280', 'TO DO'),
            'in_progress': ('#3b82f6', 'IN PROGRESS'),
            'stalled':     ('#f59e0b', 'STALLED'),
            'complete':    ('#10b981', 'COMPLETE'),
        }
        color, label = colors.get(obj.status, ('#6b7280', obj.status.upper()))
        return format_html(
            '<span style="color:{}; font-weight:600; font-size:11px;">{}</span>',
            color, label
        )
    
    @admin.display(description='Priority')
    def priority_badge(self, obj):
        colors = {'high': '#ef4444', 'medium': '#f59e0b', 'low': '#6b7280'}
        color = colors.get(obj.priority, '#6b7280')
        return format_html(
            '<span style="color:{};">●</span> {}',
            color, obj.get_priority_display()
        )
    
    @admin.display(description='Overdue', boolean=True)
    def overdue_flag(self, obj):
        return obj.is_overdue
    
    @admin.action(description='Mark selected tasks as complete')
    def mark_complete(self, request, queryset):
        for task in queryset:
            task.mark_complete()
        self.message_user(request, f'{queryset.count()} task(s) marked complete.')

    @admin.action(description='Mark selected tasks as In Progress')
    def mark_in_progress(self, request, queryset):
        queryset.update(status=Task.STATUS_IN_PROGRESS)
        self.message_user(request, f'{queryset.count()} task(s) set to In Progress.')

    @admin.action(description='Mark selected tasks as Stalled')
    def mark_stalled(self, request, queryset):
        for task in queryset:
            task.mark_stalled()
        self.message_user(request, f'{queryset.count()} task(s) marked Stalled.')
