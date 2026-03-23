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

# Maps Python weekday() → our day codes
WEEKDAY_MAP = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']


class Routine(models.Model):
    name = models.CharField(max_length=100)
    slot = models.CharField(max_length=10, choices=SLOT_CHOICES, default=SLOT_MORNING)

    # Stored as comma-separated day codes, e.g. "mon,tue,wed,thu,fri"
    days = models.CharField(
        max_length=27,
        default='mon,tue,wed,thu,fri,sat,sun',
        help_text='Comma-separated day codes: mon,tue,wed,thu,fri,sat,sun'
    )
    active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text='Display order within slot')

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
        today_code = WEEKDAY_MAP[d.weekday()]
        return today_code in self.get_days_list()
    
    def day_labels(self):
        """Human-readable day list, abbreviated"""
        codes = self.get_days_list()
        abbr = {
            'mon': 'Mo',
            'tue': 'Tu',
            'wed': 'We',
            'thu': 'Th',
            'fri': 'Fr',
            'sat': 'Sa',
            'sun': 'Su'
        }
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
    
    