from django.contrib import admin
from .models import NamedList, ListItem


class ListItemInline(admin.TabularInline):
    model = ListItem
    extra = 0


@admin.register(NamedList)
class NamedListAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    inlines = [ListItemInline]


@admin.register(ListItem)
class ListItemAdmin(admin.ModelAdmin):
    list_display = ('text', 'list', 'is_complete', 'created_at')
    list_filter = ('list', 'is_complete')
