from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Goal, GoalItem


class GoalItemInline(admin.TabularInline):
    model = GoalItem
    extra = 3
    fields = ['name', 'item_type', 'priority', 'due_date', 'order', 'is_active', 'is_complete']
    readonly_fields = ['completed_at',]
    ordering = ['order', 'due_date', 'name']


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'category', 'priority_badge', 'progress_bar',
        'due_date', 'overdue_flag', 'days_since_progress_display',
        'is_active', 'is_complete',
    ]
    list_filter = ['category', 'priority', 'is_active', 'is_complete']
    search_fields = ['name', 'description']
    list_editable = ['is_active',]
    readonly_fields = ['created_at', 'updated_at', 'completed_at', 'last_progress']
    date_hierarchy = 'due_date'
    inlines = [GoalItemInline]

    fieldsets = [
        (None, {
            'fields': ['name', 'description'],
        }),
        ('Classification', {
            'fields': ['category', 'priority'],
        }),
        ('Timeline', {
            'fields': ['start_date', 'due_date'],
        }),
        ('State', {
            'fields': ['is_active', 'is_complete', 'completed_at', 'last_progress'],
        }),
        ('Timestamps', {
            'classes': ['collapse',],
            'fields': ['created_at', 'updated_at'],
        }),
    ]

    actions = ['mark_complete', 'send_to_backburner']

    @admin.display(description='Priority')
    def priority_badge(self, obj):
        colors = {'high': '#ef4444', 'medium': '#f59e0b', 'low': '#6b7280'}
        color = colors.get(obj.priority, '#6b7280')
        return format_html(
            '<span style="color:{};">●</span> {}',
            color, obj.get_priority_display()
        )
    
    @admin.display(description='Progress')
    def progress_bar(self, obj):
        pct = obj.completion_pct()
        color = '#10b981' if pct >= 75 else '#f59e0b' if pct >= 40 else '#ef4444'
        return format_html(
            '<div style="width:120px; background:#1f2937; border-radius:3px; height:8px;">'
            '<div style="width:{}%; background:{}; height:8px; border-radius:3px;"></div>'
            '</div>'
            '<span style="font-size:11px; color:{}; margin-left:6px;">{}%</span>',
            pct, color, color, pct
        )
    
    @admin.display(description='Overdue', boolean=True)
    def overdue_flag(self, obj):
        return obj.is_overdue
    

    @admin.display(description='Stalled')
    def days_since_progress_display(self, obj):
        days = obj.days_since_progress
        if days is None:
            return format_html('<span style="{}">Never</span>', 'color:#6b7280;')
        if days > 14:
            return format_html('<span style="color:#ef4444;">{}d ago</span>', days)
        if days > 7:
            return format_html('<span style="color:#f59e0b;">{}d ago</span>', days)
        return format_html('<span style="color:#10b981;">{}d ago</span>', days)
    

    @admin.action(description='Mark selected goals Complete')
    def mark_complete(self, request, queryset):
        queryset.update(is_complete=True, completed_at=timezone.now())
        self.message_user(request, f'{queryset.count()} goal(s) marked Complete.')
    

    @admin.action(description='Move to back burner (deactivate)')
    def send_to_back_burner(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'{queryset.count()} goal(s) moved to back burner.')
    

@admin.register(GoalItem)
class GoalItemAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'goal', 'item_type', 'priority_badge',
        'due_date', 'overdue_flag', 'is_active', 'is_complete',
    ]
    list_filter = ['item_type', 'priority', 'is_active', 'is_complete', 'goal']
    search_fields = ['name', 'description', 'goal__name']
    list_editable = ['is_active',]
    readonly_fields = ['created_at', 'updated_at', 'completed_at']
    ordering = ['goal', 'order', 'due_date', 'name']

    actions = ['mark_complete']

    @admin.display(description='Priority')
    def priority_badge(self, obj):
        if not obj.priority:
            return '—'
        colors = {'high': '#ef4444', 'medium': '#f59e0b', 'low': '#6b7280'}
        color = colors.get(obj.priority, '#6b7280')
        return format_html('<span style="color:{};">●</span> {}', color, obj.get_priority_display())

    @admin.display(description='Overdue', boolean=True)
    def overdue_flag(self, obj):
        return obj.is_overdue
    
    @admin.action(description='Mark selected items as Complete')
    def mark_complete(self, request, queryset):
        for item in queryset:
            item.mark_complete()
        self.message_user(request, f'{queryset.count()} item(s) marked Complete.')

