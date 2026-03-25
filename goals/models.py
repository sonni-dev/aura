from django.db import models
from django.utils import timezone
 
 
CATEGORY_THERAPY  = 'therapy'
CATEGORY_WORK     = 'work'
CATEGORY_CAREER   = 'career'
CATEGORY_PERSONAL = 'personal'
CATEGORY_ROUTINE  = 'routine'
CATEGORY_FINANCE  = 'finance'
CATEGORY_HEALTH   = 'health'
CATEGORY_CHOICES  = [
    (CATEGORY_THERAPY,  'Therapy'),
    (CATEGORY_WORK,     'Work'),
    (CATEGORY_CAREER,   'Career'),
    (CATEGORY_PERSONAL, 'Personal'),
    (CATEGORY_ROUTINE,  'Routine'),
    (CATEGORY_FINANCE,  'Finance'),
    (CATEGORY_HEALTH,   'Health'),
]
 
PRIORITY_LOW    = 'low'
PRIORITY_MEDIUM = 'medium'
PRIORITY_HIGH   = 'high'
PRIORITY_CHOICES = [
    (PRIORITY_LOW,    'Low'),
    (PRIORITY_MEDIUM, 'Medium'),
    (PRIORITY_HIGH,   'High'),
]


class Goal(models.Model):
    """
    A longer-horizon objective made up of GoalItems (milestones / tasks).
 
    is_complete is set automatically when all active GoalItems are complete
    — call check_completion() after any GoalItem save.
 
    last_progress is updated by a post_save signal on GoalItem whenever one
    is marked complete. Celery uses this field to fire stalled-progress
    reminders when no GoalItem has been touched in N days.
 
    Reminders (e.g. 'monthly eval reminder') are created in the reminders
    app and point back here via Reminder.goal FK.
    """

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=15, choices=CATEGORY_CHOICES, blank=True)
    priority = models.CharField(max_length=15, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)

    start_date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True, help_text='Target completion date')

    is_active = models.BooleanField(default=True, help_text='Uncheck to move a goal to the back-burner without deleting.')
    is_complete = models.BooleanField(default=False)

    last_progress = models.DateField(null=True, blank=True, help_text='Date of the most recent GoalItem completion.' \
    'Auto-updated via post_save signal.')

    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        ordering = ['-priority', 'due_date', 'name']
        verbose_name = 'Goal'
        verbose_name_plural = 'Goals'

    def __str__(self):
        return self.name
    
    # ── Progress helpers ──────────────────────────────────────────────────
    def completion_pct(self):
        """Percentage of active GoalItems that are complete."""
        items = self.items.filter(is_active=True)
        total = items.count()
        if total == 0:
            return 0
        done = items.filter(is_complete=True).count()
        return round((done / total) * 100)
    
    def check_completion(self):
        """
        Mark the Goal complete if every active GoalItem is done.
        Call this after any GoalItem.mark_complete().
        """
        items = self.items.filter(is_active=True)
        if items.exists() and not items.filter(is_complete=False).exists():
            self.is_complete  = True
            self.completed_at = timezone.now()
            self.save()

    @property
    def is_overdue(self):
        if self.due_date and not self.is_complete:
            return self.due_date < timezone.now().date()
        return False
    
    @property
    def days_since_progress(self):
        """How many days since any GoalItem was completed. None if never."""
        if not self.last_progress:
            return None
        return (timezone.now().date() - self.last_progress).days


