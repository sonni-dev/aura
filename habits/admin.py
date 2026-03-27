from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from datetime import date
from .models import Habit, HabitLog



class HabitLogInline(admin.TabularInline):
    model = HabitLog
    extra = 1
    fields = ['logged_on', 'yn_value', 'scale_value', 'logged_at']
    readonly_fields = ['logged_at',]
    ordering = ['-logged_on',]
    max_num = 30    # Keep the inline manageable


@admin.register(Habit)
class HabitAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'category', 'metric_type', 'frequency',
        'logged_today_display', 'streak_display', 'completion_rate_display',
        'is_active', 'order',
    ]
    list_filter = ['metric_type', 'frequency', 'category', 'is_active']
    search_fields = ['name', 'description']
    list_editable = ['is_active', 'order']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [HabitLogInline]

    fieldsets = [
        (None, {
            'fields': ['name', 'description'],
        }),
        ('Tracking', {
            'fields': ['metric_type', 'frequency', 'category', 'order'],
        }),
        ('Dates', {
            'fields': ['start_date', 'end_date'],
        }),
        ('State', {
            'fields': ['is_active',],
        }),
        ('Timestamps', {
            'classes': ['collapse',],
            'fields': ['created_at', 'updated_at'],
        }),
    ]

    actions = ['log_yes_today', 'log_no_today']

    @admin.display(description='Logged Today', boolean=True)
    def logged_today_display(self, obj):
        return obj.is_logged_today()
    

    @admin.display(description='Streak')
    def streak_display(self, obj):
        s = obj.streak()
        if s == 0:
            return format_html('<span style="{}">0</span>', 'color:#6b7280;')
        return format_html('<span style="color:#f59e0b;">🔥 {}d</span>', s)
    

    @admin.display(description='30-day Rate')
    def completion_rate_display(self, obj):
        rate = obj.completion_rate(30)
        color = '#10b981' if rate >= 70 else '#f59e0b' if rate >= 40 else '#ef4444'
        return format_html('<span style="color:{};">{}%</span>', color, rate)
    

    @admin.action(description='Log YES for selected habits today (yn habits)')
    def log_yes_today(self, request, queryset):
        count = 0
        for habit in queryset.filter(metric_type=Habit.METRIC_YN):
            habit.log_today(yn_value=True)
            count += 1
        self.message_user(request, f'{count} habit(s) logged as YES for today.')


    @admin.action(description='Log NO for selected habits today (yn habits)')
    def log_no_today(self, request, queryset):
        count = 0
        for habit in queryset.filter(metric_type=Habit.METRIC_YN):
            habit.log_today(yn_value=False)
            count += 1
        self.message_user(request, f'{count} habit(s) logged as NO for today.')


@admin.register(HabitLog)
class HabitLogAdmin(admin.ModelAdmin):
    list_display = ['habit', 'logged_on', 'value_display', 'logged_at']
    list_filter = ['habit', 'logged_on', 'yn_value']
    search_fields = ['habit__name',]
    date_hierarchy = 'logged_on'
    ordering = ['-logged_on', 'habit']
    readonly_fields = ['logged_at',]

    @admin.display(description='Value')
    def value_display(self, obj):
        v = obj.display_value()
        if v == 'yes':
            return format_html('<span style="color:#10b981; font-weight:600;">{}</span>', 'YES')
        if v == 'no':
            return format_html('<span style="color:#ef4444; font-weight:600;">{}</span>', 'NO')
        if v == '—':
            return format_html('<span style="{}">—</span>', 'color:#6b7280;')
        return format_html('<span style="color:#f59e0b;">{}/10</span>', v)
