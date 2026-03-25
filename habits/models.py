from django.db import models
from django.utils import timezone
from datetime import date, timedelta
 
 
CATEGORY_SELF_IMPROVEMENT = 'self_improvement'
CATEGORY_HEALTH           = 'health'
CATEGORY_SPENDING         = 'spending'
CATEGORY_MENTAL           = 'mental'
CATEGORY_PHYSICAL         = 'physical'
CATEGORY_CHOICES = [
    (CATEGORY_SELF_IMPROVEMENT, 'Self-Improvement'),
    (CATEGORY_HEALTH,           'Health'),
    (CATEGORY_SPENDING,         'Spending / Financial'),
    (CATEGORY_MENTAL,           'Mental'),
    (CATEGORY_PHYSICAL,         'Physical'),
]
 
FREQ_DAILY   = 'daily'
FREQ_WEEKLY  = 'weekly'
FREQ_CUSTOM  = 'custom'
FREQ_CHOICES = [
    (FREQ_DAILY,  'Daily'),
    (FREQ_WEEKLY, 'Weekly'),
    (FREQ_CUSTOM, 'Custom'),
]


class Habit(models.Model):
    """
    Defines a habit to track. metric_type controls what gets recorded in
    HabitLog:
      - 'yn'    → boolean (did you / didn't you)
      - 'scale' → integer 1-10 (how productive, how anxious, how rested)
 
    Keeping both types on one model lets the dashboard render them
    differently (dot-grid for yn, sparkline for scale) without any
    schema changes.
 
    Reminders are created in the reminders app and point back here via
    Reminder.habit FK.
 
    Example yn habits:    shower, left house, no delivery, no drink, gummy
    Example scale habits: productivity, anxiety level, rest quality
    """

    METRIC_YN = 'yn'
    METRIC_SCALE = 'scale'
    METRIC_CHOICES = [
        (METRIC_YN,    'Yes / No'),
        (METRIC_SCALE, 'Scale (1-10)'),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, blank=True)
    metric_type = models.CharField(max_length=5, choices=METRIC_CHOICES, default=METRIC_YN)
    frequency = models.CharField(max_length=15, choices=FREQ_CHOICES, default=FREQ_DAILY)

    start_date = models.DateField(default=date.today)
    end_date = models.DateField(null=True, blank=True, help_text='Leave blank for an ongoing habit.')
    
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text='Display order on the dashboard habit grid.')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Habit'
        verbose_name_plural = 'Habits'

    def __str__(self):
        return f'{self.name} ({self.get_metric_type_display()})'
    
    
    # ── Log helpers ───────────────────────────────────────────────────────
 
    def log_today(self, yn_value=None, scale_value=None, for_date=None):
        """
        Create or update today's log entry. Pass yn_value (bool) for yn
        habits, or scale_value (int 1–10) for scale habits.
        Returns the HabitLog instance.
        """
        d = for_date or date.today()
        log, _ = HabitLog.objects.update_or_create(
            habit=self,
            logged_on=d,
            defaults={
                'yn_value':    yn_value,
                'scale_value': scale_value,
            }
        )
        return log
 
    def is_logged_today(self, for_date=None):
        d = for_date or date.today()
        return HabitLog.objects.filter(habit=self, logged_on=d).exists()
 
    def get_log(self, for_date=None):
        """Return today's HabitLog or None."""
        d = for_date or date.today()
        return HabitLog.objects.filter(habit=self, logged_on=d).first()
 

    # ── Stats helpers ─────────────────────────────────────────────────────

    def logs_for_week(self, for_date=None):
        """Return a list of 7 HabitLog-or-None values, Mon -> Sun of the current week."""
        d = for_date or date.today()
        week_start = d - timedelta(days=d.weekday())  # Monday
        days = [week_start + timedelta(days=i) for i in range(7)]
        logs = {
            log.logged_on: log 
            for log in HabitLog.objects.filter(habit=self, logged_on__in=days)
        }
        return [logs.get(day) for day in days]
    
    def completion_rate(self, days=30):
        """
        Percentage of days in the last N days that have a positive log:
          - yn habits:    yn_value=True counts as done
          - scale habits: any log counts as done
        """
        since  = date.today() - timedelta(days=days)
        qs     = HabitLog.objects.filter(habit=self, logged_on__gte=since)
        if self.metric_type == self.METRIC_YN:
            done = qs.filter(yn_value=True).count()
        else:
            done = qs.count()
        return round((done / days) * 100)
    
    def streak(self, for_date=None):
        """
        Consecutive days ending yesterday on which the habit was positively
        logged. Today is excluded — it may not be logged yet.
        """
        d      = (for_date or date.today()) - timedelta(days=1)
        streak = 0
        for _ in range(365):
            log = HabitLog.objects.filter(habit=self, logged_on=d).first()
            logged = False
            if log:
                if self.metric_type == self.METRIC_YN:
                    logged = bool(log.yn_value)
                else:
                    logged = log.scale_value is not None
            if logged:
                streak += 1
                d -= timedelta(days=1)
            else:
                break
        return streak


class HabitLog(models.Model):
    """
    One record per habit per day. The unique_together constraint prevents
    duplicate entries. Only one of yn_value / scale_value will be populated
    depending on the parent Habit's metric_type.
    """

    habit = models.ForeignKey(Habit, on_delete=models.CASCADE, related_name='logs')
    logged_on = models.DateField(default=date.today)
    
    yn_value = models.BooleanField(null=True, blank=True, help_text='Set for yes/no habits. True = done, False = not done.')
    scale_value = models.IntegerField(null=True, blank=True, help_text='Set for scale habits. Integer 1-10.')

    logged_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        unique_together = ('habit', 'logged_on')
        ordering = ['-logged_on']
        verbose_name = 'Habit Log'
        verbose_name_plural = 'Habit Logs'

    def __str__(self):
        return f'{self.habit.name} — {self.logged_on}'
    

    def display_value(self):
        """Human-readable log value for admin and API serialization."""
        if self.habit.metric_type == Habit.METRIC_YN:
            if self.yn_value is None:
                return '—'
            return 'yes' if self.yn_value else 'no'
        return str(self.scale_value) if self.scale_value is not None else '—'
