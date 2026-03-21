from django.db import models
from django.utils import timezone

class Reminder(models.Model):
    RECURRENCE_NONE = 'none'
    RECURRENCE_DAILY = 'daily'
    RECURRENCE_WEEKLY = 'weekly'
    RECURRENCE_MONTHLY = 'monthly'
    RECURRENCE_CHOICES = [
        (RECURRENCE_NONE, 'One-time'),
        (RECURRENCE_DAILY, 'Daily'),
        (RECURRENCE_WEEKLY, 'Weekly'),
        (RECURRENCE_MONTHLY, 'Monthly'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    remind_at = models.DateTimeField()
    recurrence = models.CharField(
        max_length=10, choices=RECURRENCE_CHOICES, default=RECURRENCE_NONE
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['remind_at']
        verbose_name = 'Reminder'
        verbose_name_plural = 'Reminders'

    def __str__(self):
        return self.title

    @property
    def is_upcoming_today(self):
        now = timezone.now()
        return self.active and self.remind_at.date() == now.date() and self.remind_at >= now

    @property
    def is_due_now(self):
        """True if reminder is within 15 minutes from now."""
        now = timezone.now()
        delta = self.remind_at - now
        return self.active and 0 <= delta.total_seconds() <= 900

