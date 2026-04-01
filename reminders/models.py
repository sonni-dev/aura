from django.db import models
from django.utils import timezone
from dateutil.relativedelta import relativedelta
 
 
class Reminder(models.Model):
    """
    Universal scheduling engine. Any model that needs recurring alerts
    or one-time notifications creates a Reminder and links back to itself
    via the appropriate nullable FK.
 
    Completion is tracked via is_complete / completed_at. Call dismiss() to
    mark a reminder done — it will also propagate completion to the linked
    source object (Task, GoalItem, or RoutineItem) unless sync_source=False.
 
    Source models call their own dismiss logic via bulk .update() to avoid
    triggering a recursive loop.
 
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

    # ── Completion ────────────────────────────────────────────────────────
    is_complete = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)


    # ── Source model FKs (at most one will be set) ────────────────────────
    #
    # Hierarchy for granularity:
    #   task         → a standalone Task
    #   goal_item    → a single step inside a Goal
    #   goal         → the whole Goal (e.g. "monthly eval" reminder)
    #   routine_item → a single RoutineItem that needs a timely nudge
    #   routine      → the whole Routine (e.g. "start your evening routine")
    #   habit        → a Habit
    #
    # Leave all blank for a standalone reminder.


    task    = models.ForeignKey(
        'tasks.Task',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='reminders',
    )

    routine_item = models.ForeignKey('routines.RoutineItem', null=True, blank=True, on_delete=models.CASCADE, related_name='reminders')
    routine = models.ForeignKey(
        'routines.Routine',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='reminders',
    )

    goal_item = models.ForeignKey('goals.GoalItem', null=True, blank=True, on_delete=models.CASCADE, related_name='reminders')
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
        status = ' ✓' if self.is_complete else ''
        return f'{self.title} ({self.frequency}){status}'
    
    def save(self, *args, **kwargs):
        if not self.next_run:
            self.next_run = self.start_date
        super().save(*args, **kwargs)
    
     # ── Introspection helpers ─────────────────────────────────────────────
 
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
        """
        Return whichever source object owns this reminder, or None.
        Item-level FKs are checked before parent-level ones so the most
        specific source is returned when both are set (e.g. goal_item + goal).
        """
        return (
            self.task
            or self.goal_item
            or self.goal
            or self.routine_item
            or self.routine
            or self.habit
        )
    
    @property
    def source_label(self):
        """Human-readable type label for the linked source, e.g. 'Task'."""
        if self.task_id:            return 'Task'
        if self.goal_item_id:       return 'Goal Item'
        if self.goal_id:            return 'Goal'
        if self.routine_item_id:    return 'Routine Item'
        if self.routine_id:         return 'Routine'
        if self.habit_id:           return 'Habit'


    # ── Completion helpers ────────────────────────────────────────────────
    
    def dismiss(self, sync_source=True):
        """
        Mark this reminder as complete/dismissed and deactivate it.
 
        If sync_source=True (default), also propagates completion to the
        linked source object:
          - Task        → task.mark_complete()
          - GoalItem    → goal_item.mark_complete()
          - RoutineItem → routine_item.toggle_today() if not already done today
 
        Goal / Routine / Habit level reminders are one-directional: dismissing
        the reminder does not auto-complete the entire goal/routine/habit
        (too coarse). Source models call dismiss(sync_source=False) when they
        bulk-update reminders to avoid triggering a recursive loop.
        """
        if self.is_complete:
            return  # already dismissed - nothihng to do
        
        now = timezone.now()
        self.is_complete = True
        self.completed_at = now
        self.is_active = False
        self.save(update_fields=['is_complete', 'completed_at', 'is_active', 'updated_at'])

        if not sync_source:
            return
    
        # ── Propagate to source ──────────────────────────────────────────
        if self.task_id and not self.task.is_complete:
            self.task.mark_complete()
        
        elif self.goal_item_id and not self.goal_item.is_complete:
            self.goal_item.mark_complete()

        elif self.routine_item_id and not self.routine_item.is_done_today():
            self.routine_item.toggle_today()