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
 
    last_progress is updated inside GoalItem.mark_complete() (not via signals,
    to avoid import-order issues). Celery uses this field to fire
    stalled-progress reminders when no GoalItem has been touched in N days.
 
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
    'Auto-updated inside mark_complete().')

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
 
        Also bulk-dismisses any goal-level Reminders (Reminder.goal = self)
        that haven't been dismissed yet, since the goal is now done.
        """
        items = self.items.filter(is_active=True)
        if items.exists() and not items.filter(is_complete=False).exists():
            self.is_complete  = True
            self.completed_at = timezone.now()
            self.save()

            # Dismiss goal-level reminders (whole-goal links, not goal_item links)
            self.reminders.filter(is_complete=False).update(
                is_complete=True,
                is_active=False,
                completed_at=timezone.now(),
            )


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



class GoalItem(models.Model):
    """
    A concrete step, milestone, or blocking task within a Goal.
 
    item_type lets you distinguish tasks from milestones so the dashboard
    can render a timeline vs. a simple checklist depending on type mix.
 
    Reminders tied to a specific GoalItem (rather than the whole Goal) use
    Reminder.goal_item FK. mark_complete() dismisses those automatically.
    """

    TYPE_TASK      = 'task'
    TYPE_MILESTONE = 'milestone'
    TYPE_BLOCKING  = 'blocking'
    TYPE_CHOICES   = [
        (TYPE_TASK,      'Task'),
        (TYPE_MILESTONE, 'Milestone'),
        (TYPE_BLOCKING,  'Blocking Task'),
    ]

    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    item_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_TASK)
    priority = models.CharField(max_length=15, choices=PRIORITY_CHOICES, blank=True)
    due_date = models.DateField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True, help_text='Uncheck to move item to back burner without deleting.')
    is_complete = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        ordering = ['order', 'due_date', 'name']
        verbose_name = 'Goal Item'
        verbose_name_plural = 'Goal Items'
    
    def __str__(self):
        return f'{self.goal.name} > {self.name}'
    

    def mark_complete(self):
        """
        Mark this item complete, dismiss linked Reminders, update
        Goal.last_progress, then check whether the parent Goal is now done.
 
        Uses a direct queryset .update() on reminders to avoid calling
        Reminder.dismiss() (which would call mark_complete() again).
        """
        # idempotent guard
        if self.is_complete:
            return
        
        self.is_complete  = True
        self.completed_at = timezone.now()
        self.save()

        # Bulk-dismiss reminders tied to this specific goal item
        self.reminders.filter(is_complete=False).update(
            is_complete=True,
            is_active=False,
            completed_at=timezone.now(),
        )
 
        # Keep last_progress current on the parent goal
        goal = self.goal
        goal.last_progress = timezone.now().date()
        goal.save(update_fields=['last_progress', 'updated_at'])
 
        # Auto-complete the goal if all items are done
        goal.check_completion()
    
    @property
    def is_overdue(self):
        if self.due_date and not self.is_complete:
            return self.due_date < timezone.now().date()
        return False
