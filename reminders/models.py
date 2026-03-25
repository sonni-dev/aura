from django.db import models
from django.utils import timezone
from dateutil.relativedelta import relativedelta
 
 
class Reminder(models.Model):
    """
    Universal scheduling engine. Any model that needs recurring alerts
    or one-time notifications creates a Reminder and links back to itself
    via the appropriate nullable FK.
 
    Celery Beat polls this table every minute via process_due_reminders()
    in reminders/tasks.py. Channel controls how the alert is delivered —
    'in_app' is the default; 'sms' plugs in Twilio later without touching
    any source-model code.
    """

    FREQ_ONCE    = 'once'
    FREQ_DAILY   = 'daily'
    FREQ_WEEKLY  = 'weekly'
    FREQ_MONTHLY = 'monthly'
    FREQ_CUSTOM  = 'custom'
    FREQ_CHOICES = [
        (FREQ_ONCE,    'One-time'),
        (FREQ_DAILY,   'Daily'),
        (FREQ_WEEKLY,  'Weekly'),
        (FREQ_MONTHLY, 'Monthly'),
        (FREQ_CUSTOM,  'Custom Interval'),
    ]
 
    CHANNEL_IN_APP = 'in_app'
    CHANNEL_SMS    = 'sms'
    CHANNEL_PUSH   = 'push'
    CHANNEL_CHOICES = [
        (CHANNEL_IN_APP, 'In-App'),
        (CHANNEL_SMS,    'SMS (Twilio)'),
        (CHANNEL_PUSH,   'Push Notification'),
    ]
 
    # ── Core fields ──────────────────────────────────────────────────────

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default=CHANNEL_IN_APP)

    # ── Scheduling fields ─────────────────────────────────────────────────
    frequency  = models.CharField(
        max_length=10, choices=FREQ_CHOICES, default=FREQ_ONCE
    )
    interval   = models.PositiveIntegerField(
        default=1,
        help_text='Every N units (e.g. interval=2 + frequency=weekly → every 2 weeks)'
    )
    start_date = models.DateTimeField(default=timezone.now)
    next_run   = models.DateTimeField(null=True, blank=True)
    last_run   = models.DateTimeField(null=True, blank=True)
    is_active  = models.BooleanField(default=True)


    # ── Source model FKs (at most one will be set) ────────────────────────
    task    = models.ForeignKey(
        'tasks.Task',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='reminders',
    )
    routine = models.ForeignKey(
        'routines.Routine',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='reminders',
    )
    goal    = models.ForeignKey(
        'goals.Goal',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='reminders',
    )
    habit   = models.ForeignKey(
        'habits.Habit',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='reminders',
    )
 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        ordering = ['next_run']
        verbose_name = 'Reminder'
        verbose_name_plural = 'Reminders'

    def __str__(self):
        return f'{self.title} ({self.frequency})'
    
    def save(self, *args, **kwargs):
        if not self.next_run:
            self.next_run = self.start_date
        super().save(*args, **kwargs)
    
    # ── Scheduling helpers ────────────────────────────────────────────────
 
    def advance_next_run(self):
        """
        Call after this reminder fires. Pushes next_run forward based on
        frequency + interval, or deactivates if one-time.
        """
        now = timezone.now()
 
        if self.frequency == self.FREQ_DAILY:
            self.next_run = now + relativedelta(days=self.interval)
        elif self.frequency == self.FREQ_WEEKLY:
            self.next_run = now + relativedelta(weeks=self.interval)
        elif self.frequency == self.FREQ_MONTHLY:
            self.next_run = now + relativedelta(months=self.interval)
        elif self.frequency == self.FREQ_ONCE:
            self.is_active = False
        # FREQ_CUSTOM: caller is responsible for setting next_run manually
 
        self.last_run = now
        self.save()


    @property
    def is_due(self):
        """True if this reminder is active and past its next_run time."""
        return self.is_active and self.next_run and self.next_run <= timezone.now()

    @property
    def is_urgent(self):
        """True if reminder is within the next 15 minutes."""
        if not self.is_active or not self.next_run:
            return False
        delta = self.next_run - timezone.now()
        return 0 <= delta.total_seconds() <= 900
    
    @property
    def source(self):
        """Return whichever source object owns this reminder, or None."""
        return self.task or self.routine or self.goal or self.habit


