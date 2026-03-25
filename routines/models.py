from django.db import models
from django.utils import timezone
from datetime import date, timedelta


SLOT_MORNING = 'morning'
SLOT_AFTERNOON = 'afternoon'
SLOT_EVENING = 'evening'
SLOT_CHOICES = [
    (SLOT_MORNING, 'Morning'),
    (SLOT_AFTERNOON, 'Afternoon'),
    (SLOT_EVENING, 'Evening'),
]

DAY_CHOICES = [
    ('mon', 'Monday'),
    ('tue', 'Tuesday'),
    ('wed', 'Wednesday'),
    ('thu', 'Thursday'),
    ('fri', 'Friday'),
    ('sat', 'Saturday'),
    ('sun', 'Sunday'),
]

# Maps Python weekday() → my day codes
WEEKDAY_MAP = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

DAY_CHOICES = [
    ('mon', 'Monday'),
    ('tue', 'Tuesday'),
    ('wed', 'Wednesday'),
    ('thu', 'Thursday'),
    ('fri', 'Friday'),
    ('sat', 'Saturday'),
    ('sun', 'Sunday'),
]

# ── Category choices (used on RoutineItem) ────────────────────────────────
CATEGORY_BODY       = 'body'
CATEGORY_SELF_CARE  = 'self_care'
CATEGORY_HYGIENE    = 'hygiene'
CATEGORY_FOOD       = 'food'
CATEGORY_WORK       = 'work'
CATEGORY_CODE       = 'code'
CATEGORY_CLEANING   = 'cleaning'
CATEGORY_PET        = 'pet'
CATEGORY_BEDTIME    = 'bedtime'
CATEGORY_WAKEUP     = 'wakeup'
CATEGORY_OTHER      = 'other'
CATEGORY_CHOICES = [
    (CATEGORY_BODY,      'Body'),
    (CATEGORY_SELF_CARE, 'Self-Care'),
    (CATEGORY_HYGIENE,   'Hygiene'),
    (CATEGORY_FOOD,      'Food / Meals'),
    (CATEGORY_WORK,      'Work'),
    (CATEGORY_CODE,      'Code / Career'),
    (CATEGORY_CLEANING,  'Cleaning / Maintenance'),
    (CATEGORY_PET,       'Pet'),
    (CATEGORY_BEDTIME,   'Bedtime'),
    (CATEGORY_WAKEUP,    'Wake Up'),
    (CATEGORY_OTHER,     'Other'),
]


class Routine(models.Model):
    """
    A named block of items that recurs on specific days of the week,
    anchored to a time slot (morning / afternoon / evening).
 
    Reminders are created separately in the reminders app and point back
    here via Reminder.routine FK — no reminder FK needed on this model.
 
    Examples: Weekday Morning Routine, Weekend Evening Routine,
              Weekly Cleaning Routine.
    """

    name = models.CharField(max_length=100)
    slot = models.CharField(max_length=10, choices=SLOT_CHOICES, default=SLOT_MORNING)

    # Stored as comma-separated day codes, e.g. "mon,tue,wed,thu,fri"
    days = models.CharField(
        max_length=27,
        default='mon,tue,wed,thu,fri,sat,sun',
        help_text='Comma-separated day codes: mon,tue,wed,thu,fri,sat,sun'
    )
    active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text='Display order within slot on the dashboard.')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['slot', 'order', 'name']
        verbose_name = 'Routine'
        verbose_name_plural = 'Routines'
    
    def __str__(self):
        return f'{self.name} ({self.get_slot_display()})'
    
    # ------------ DAY HELPERS ------------

    def get_days_list(self):
        """Return list of day coes, e.g. ['mon', 'tue', 'fri']."""
        return [d.strip() for d in self.days.split(',') if d.strip()]
    
    def set_days_list(self, days_list):
        self.days = ','.join(days_list)
    
    def runs_today(self, for_date=None):
        d = for_date or timezone.now().date()
        return WEEKDAY_MAP[d.weekday()] in self.get_days_list()
    
    def day_labels(self):
        """Abbreviated day labels for display, e.g. 'Mo Tu We Th Fr'."""
        abbr = {'mon':'Mo','tue':'Tu','wed':'We','thu':'Th','fri':'Fr','sat':'Sa','sun':'Su'}
        codes = self.get_days_list()
        return ' '.join(abbr[c] for c in abbr if c in codes)
    
    # ------------ PROGRESS HELPERS ------------

    def today_progress(self, for_date=None):
        """Returns (completed_count, total_count) for active items today"""
        d = for_date or timezone.now().date()
        items = self.items.filter(active=True)
        total = items.count()
        done = RoutineCompletion.objects.filter(
            item__in=items, completed_on=d
        ).count()
        return done, total
    
    def completion_pct(self, for_date=None):
        done, total = self.today_progress(for_date)
        if total == 0:
            return 0
        return round((done / total) * 100)

    def streak(self, for_date=None):
        """
        Count consecutive days (going backwards from yesterday) on which
        ALL active items in this routine were completed.
        Today is not counted -- it may still be in progress.
        """
        d = (for_date or timezone.now().date()) - timedelta(days=1)
        items = list(self.items.filter(active=True))
        item_count = len(items)
        if item_count == 0:
            return 0
        
        streak = 0
        # Only check days this routine was scheduled to run
        for _ in range(365):
            day_code = WEEKDAY_MAP[d.weekday()]
            if day_code in self.get_days_list():
                done = RoutineCompletion.objects.filter(
                    item__in=items, completed_on=d
                ).count()
                if done >= item_count:
                    streak += 1
                else:
                    break
            d -= timedelta(days=1)
        return streak


class RoutineItem(models.Model):
    routine = models.ForeignKey(Routine, on_delete=models.CASCADE, related_name='items')
    title = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)


    class Meta:
        ordering = ['order', 'title']
        verbose_name = 'Routine Item'
        verbose_name_plural = 'Routine Items'
    
    def __str__(self):
        return f'{self.routine.name} > {self.title}'
    
    def is_done_today(self, for_date=None):
        d = for_date or timezone.now().date()
        return RoutineCompletion.objects.filter(item=self, completed_on=d).exists()
    
    def item_streak(self, for_date=None):
        """Consecutive days this individual item was completed (before today)"""
        d = (for_date or timezone.now().date()) - timedelta(days=1)
        streak = 0
        for _ in range(365):
            if RoutineCompletion.objects.filter(item=self, completed_on=d).exists():
                streak += 1
                d -= timedelta(days=1)
            else:
                break
        return streak
    

class RoutineCompletion(models.Model):
    item = models.ForeignKey(RoutineItem, on_delete=models.CASCADE, related_name='completions')
    completed_on = models.DateField(default=date.today)
    completed_at = models.DateTimeField(auto_now_add=True)

    
    class Meta:
        unique_together = ('item', 'completed_on')
        ordering = ['-completed_on']
        verbose_name = 'Completion'
        verbose_name_plural = 'Completions'
    
    def __str__(self):
        return f'{self.item} -- {self.completed_on}'