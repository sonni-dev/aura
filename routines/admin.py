from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Routine, RoutineItem, RoutineCompletion



class RoutineItemInline(admin.TabularInline):
    model = RoutineItem
    extra = 3
    fields = ('title', 'category', 'order', 'is_active')
    ordering = ('order', 'title')


@admin.register(Routine)
class RoutineAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'slot', 'day_labels_display', 'item_count',
        'today_progress_display', 'streak_display', 'is_active', 'order',
    ]
    list_filter = ['slot', 'is_active']
    search_fields = ['name',]
    list_editable = ['is_active', 'order']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [RoutineItemInline]


    fieldsets = [
        (None, {
            'fields': ['name', 'slot', 'order', 'is_active'],
        }),
        ('Schedule', {
            'description': 'Comma-separated day codes: mon, tue, wed, thu, fri, sat, sun',
            'fields': ['days',],
        }),
        ('Timestamps', {
            'classes': ['collapse',],
            'fields': ['created_at', 'updated_at'],
        }),
    ]

    @admin.display(description='Days')
    def day_labels_display(self, obj):
        return obj.day_labels()
    
    @admin.display(description='Item')
    def item_count(self, obj):
        return obj.items.filter(is_active=True).count()
    
    @admin.display(description="Today's Progress")
    def today_progress_display(self, obj):
        done, total = obj.today_progress()
        if total == 0:
            return format_html('<span style="{}">—</span>', 'color:#6b7280;')
        pct = round((done / total) * 100)
        color = '#10b981' if pct == 100 else '#f59e0b' if pct > 0 else '#6b7280'
        return format_html(
            '<span style="color:{};">{}/{} ({}%)</span>',
            color, done, total, pct
        )
    
    @admin.display(description='Streak')
    def streak_display(self, obj):
        s = obj.streak()
        if s == 0:
            return format_html('<span style="{}">0</span>', 'color:#6b7280;')
        return format_html('<span style="color:#f59e0b;">🔥 {}d</span>', s)


@admin.register(RoutineItem)
class RoutineItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'routine', 'category', 'order', 'is_active', 'done_today_display']
    list_filter = ['routine', 'category', 'is_active']
    search_fields = ['title', 'routine__name']
    list_editable = ['order', 'is_active']
    ordering = ['routine', 'order', 'title']

    @admin.display(description='Done Today', boolean=True)
    def done_today_display(self, obj):
        return obj.is_done_today()


@admin.register(RoutineCompletion)
class RoutineCompletionAdmin(admin.ModelAdmin):
    list_display = ['item', 'completed_on', 'completed_at']
    list_filter = ['completed_on', 'item__routine']
    search_fields = ['item__title', 'item__routine__name']
    date_hierarchy = 'completed_on'
    ordering = ['-completed_on',]

