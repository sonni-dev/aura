from django.contrib import admin
from django.utils.html import format_html
from .models import Todo


@admin.register(Todo)
class TodoAdmin(admin.ModelAdmin):
    list_display = ('title', 'priority_badge', 'due_date', 'completed', 'is_overdue_display', 'created_at')
    list_filter = ('completed', 'priority', 'due_date')
    search_fields = ('title', 'notes')
    list_editable = ('completed',)
    date_hierarchy = 'due_date'
    ordering = ('completed', 'due_date', '-priority')
    readonly_fields = ('created_at', 'completed_at')

    fieldsets = (
        (None, {'fields': ('title', 'notes', 'priority')}),
        ('Scheduling', {'fields': ('due_date',)}),
        ('Status', {'fields': ('completed', 'completed_at', 'created_at')}),
    )

    def priority_badge(self, obj):
        colors = {'high': '#ef4444', 'medium': '#f59e0b', 'low': '#6b7280'}
        color = colors.get(obj.priority, '#6b7280')
        return format_html(
            '<span style="background:{}; color:white; padding:2px 8px; border-radius:4px; font-size:11px">{}</span>',
            color, obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'

    def is_overdue_display(self, obj):
        if obj.is_overdue:
            return format_html('<span style="color:#ef4444; font-weight:bold">⚠ Overdue</span>')
        return '—'
    is_overdue_display.short_description = 'Overdue?'
