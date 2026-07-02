from django.db import models
from django.utils import timezone


class NamedList(models.Model):
    """
    A named collection of items, e.g. 'groceries', 'packing'.
    Created on-demand the first time an item is added to a list name
    that doesn't exist yet.
    """
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'List'
        verbose_name_plural = 'Lists'

    def __str__(self):
        return self.name


class ListItem(models.Model):
    list = models.ForeignKey(NamedList, on_delete=models.CASCADE, related_name='items')
    text = models.CharField(max_length=255)
    is_complete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['is_complete', 'created_at']

    def __str__(self):
        status = ' ✓' if self.is_complete else ''
        return f"{self.text}{status}"

    def complete(self):
        self.is_complete = True
        self.completed_at = timezone.now()
        self.save(update_fields=['is_complete', 'completed_at'])
