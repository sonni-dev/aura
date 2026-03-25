from django.db import models
from django.utils import timezone

class Task(models.Model):
    """
    General-purpose to-do / task. Covers one-off tasks as well as anything
    that doesn't fit cleanly into a Routine or Goal.
 
    status auto-transitions to STALLED via Celery if updated_at falls too far
    behind (see tasks/tasks.py). Mark complete via mark_complete() to ensure
    completed_at is stamped correctly.
    """

    # ── Status ────────────────────────────────────────────────────────────
    STATUS_TODO       = 'todo'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_STALLED    = 'stalled'
    STATUS_COMPLETE   = 'complete'
    STATUS_CHOICES = [
        (STATUS_TODO,        'To Do'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_STALLED,     'Stalled'),
        (STATUS_COMPLETE,    'Complete'),
    ]

    # ── Priority ──────────────────────────────────────────────────────────
    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
    ]

    # ── Category ──────────────────────────────────────────────────────────
    CATEGORY_HOUSEHOLD = 'household'
    CATEGORY_ADULTING  = 'adulting'
    CATEGORY_ADMIN     = 'admin'
    CATEGORY_THERAPY   = 'therapy'
    CATEGORY_CAREER    = 'career'
    CATEGORY_PERSONAL  = 'personal'
    CATEGORY_CHOICES = [
        (CATEGORY_HOUSEHOLD, 'Household'),
        (CATEGORY_ADULTING,  'Adulting'),
        (CATEGORY_ADMIN,     'Admin'),
        (CATEGORY_THERAPY,   'Therapy'),
        (CATEGORY_CAREER,    'Career'),
        (CATEGORY_PERSONAL,  'Personal'),
    ]
 
    # ── Energy type ───────────────────────────────────────────────────────
    ENERGY_MENTAL   = 'mental'
    ENERGY_PHYSICAL = 'physical'
    ENERGY_SOCIAL   = 'social'
    ENERGY_CHOICES = [
        (ENERGY_MENTAL,   'Mental'),
        (ENERGY_PHYSICAL, 'Physical'),
        (ENERGY_SOCIAL,   'Social'),
    ]

    # ── Location context ──────────────────────────────────────────────────
    WHERE_HOME     = 'home'
    WHERE_OUTDOORS = 'outdoors'
    WHERE_OUT      = 'out_and_about'
    WHERE_CHOICES = [
        (WHERE_HOME,     'Home'),
        (WHERE_OUTDOORS, 'Outdoors'),
        (WHERE_OUT,      'Out and About'),
    ]


    # ── Core fields ───────────────────────────────────────────────────────
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_TODO)
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM
    )
    category = models.CharField(max_length=15, choices=CATEGORY_CHOICES, blank=True)
    energy_type = models.CharField(max_length=15, choices=ENERGY_CHOICES, blank=True, help_text='What kind of energy does this task require?')
    where_task = models.CharField(max_length=15, choices=WHERE_CHOICES, blank=True, help_text='Where does this task need to happen?')
    due_date = models.DateField(null=True, blank=True)
    
    # ── State flags ───────────────────────────────────────────────────────
    is_active = models.BooleanField(default=True, help_text='Uncheck to archive without deleting.')
    is_complete = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    

    class Meta:
        ordering = ['is_complete', 'due_date', '-priority']
        verbose_name = 'Task'
        verbose_name_plural = 'Tasks'

    def __str__(self):
        return self.name


    # ── Status helpers ────────────────────────────────────────────────────
    @property
    def is_overdue(self):
        if self.due_date and not self.is_complete:
            return self.due_date < timezone.now().date()
        return False

    def mark_complete(self):
        self.is_complete = True
        self.status = self.STATUS_COMPLETE
        self.completed_at = timezone.now()
        self.save()
    
    def mark_stalled(self):
        """Called by Celery when updated_at hasn't moved in N days."""
        if self.status == self.STATUS_IN_PROGRESS:
            self.status = self.STATUS_STALLED
            self.save()