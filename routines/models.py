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
 
    reset_mode controls completion behaviour:
      - 'daily'       → default; completion state resets at midnight.
                        Progress is measured against today's completions.
      - 'on_complete'  → session-based; a RoutineSession is opened the first
                        time an item is toggled on a scheduled day, and stays
                        open (visible on the dashboard) until ALL active items
                        are checked off. Useful for weekly cleaning routines
                        or any task-block that may span multiple days.
 
    Reminders are created separately in the reminders app and point back
    here via Reminder.routine FK — no reminder FK needed on this model.
    """

    RESET_DAILY = 'daily'
    RESET_ON_COMPLETE = 'on_complete'
    RESET_CHOICES = [
        (RESET_DAILY, 'Daily (resets each night)'),
        (RESET_ON_COMPLETE, 'On Completion (stays open until all items done)'),
    ]

    name = models.CharField(max_length=100)
    slot = models.CharField(max_length=10, choices=SLOT_CHOICES, default=SLOT_MORNING)

    # Stored as comma-separated day codes, e.g. "mon,tue,wed,thu,fri"
    days = models.CharField(
        max_length=27,
        default='mon,tue,wed,thu,fri,sat,sun',
        help_text='Comma-separated day codes: mon,tue,wed,thu,fri,sat,sun'
    )

    reset_mode = models.CharField(
        max_length=15,
        choices=RESET_CHOICES,
        default=RESET_DAILY,
        help_text=(
            'Daily: progress resets each night. '
            'On Completion: routine stays open on the dashboard until every item is checked off. '
        ),
    )

    is_active = models.BooleanField(default=True)
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
    

    # ------------ SESSION HELPERS (on_complete routines only) ------------

    def get_open_session(self):
        """Return the currently open RoutineSession, or None."""
        return self.sessions.filter(completed_at__isnull=True).first()
    
    def get_or_create_session(self):
        """
        Return the open session if one exists, otherwise open a new one
        anchored to today. Called lazily on first item toggle.
        """
        session = self.get_open_session()
        if session is None:
            session = RoutineSession.objects.create(
                routine=self,
                started_on=timezone.now().date(),
            )
        return session
    
    # ------------ PROGRESS HELPERS ------------

    def today_progress(self, for_date=None, session=None):
        """
        Returns (completed_count, total_count) for active items.
 
        For daily routines:       counts completions dated today.
        For on_complete routines: counts completions belonging to the open
                                  session (pass session= to avoid a 2nd query).
        """
        d = for_date or timezone.now().date()
        items = self.items.filter(is_active=True)
        total = items.count()

        if self.reset_mode == self.RESET_ON_COMPLETE:
            open_session = session if session is not None else self.get_open_session()
            if open_session is None:
                return 0, total
            done = RoutineCompletion.objects.filter(
                item__in=items, session=open_session
            ).count()
        else:
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
 
        For on_complete routines, counts closed sessions on scheduled days.
        Today is not counted — it may still be in progress.
        """
        
        items = list(self.items.filter(is_active=True))
        item_count = len(items)
        if item_count == 0:
            return 0
        
        if self.reset_mode == self.RESET_ON_COMPLETE:
            # Count closed sessions whose started_on was a scheduled day
            d = (for_date or timezone.now().date()) - timedelta(days=1)

            streak = 0
            # Only check days this routine was scheduled to run
            for _ in range(365):
                day_code = WEEKDAY_MAP[d.weekday()]
                if day_code in self.get_days_list():
                    closed = self.sessions.filter(
                        started_on=d,
                        completed_at__isnull=False,
                    ).exists()
                    if closed:
                        streak += 1
                    else:
                        break
                d -= timedelta(days=1)
            return streak
        else:
            d = (for_date or timezone.now().date()) - timedelta(days=1)
            streak = 0
            
            for _ in range(365):
                day_code = WEEKDAY_MAP[d.weekday()]
                if day_code in self.get_days_list():
                    done = RoutineCompletion.objects.filter(
                        item__in=items,
                        completed_on=d,
                    ).exists()
                    if done >= item_count:
                        streak += 1
                    else:
                        break
                d -= timedelta(days=1)
            return streak


class RoutineItem(models.Model):
    """
    A single action inside a Routine (e.g. 'Walk Doby', 'Brush teeth').
    Completions are tracked per-day via RoutineCompletion.

    Reminders can be linked to a specific RoutineItem via Reminder.routine_item
    FK for timely nudges that aren't tied to the whole routine.
    toggle_today() dismisses those reminders automatically when the item is
    marked complete for the day (but not when toggled back off).
    """

    routine = models.ForeignKey(Routine, on_delete=models.CASCADE, related_name='items')
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=15, choices=CATEGORY_CHOICES, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)


    class Meta:
        ordering = ['order', 'title']
        verbose_name = 'Routine Item'
        verbose_name_plural = 'Routine Items'
    
    def __str__(self):
        return f'{self.routine.name} > {self.title}'
    
    def is_done_today(self, for_date=None, session=None):
        """
        Returns True if this item is completed for the current period.
 
        For daily routines: checks for a completion dated today.
        For on_complete routines: checks for a completion in the given session
          (pass session= to avoid a DB lookup; falls back to get_open_session).
        """
        if self.routine.reset_mode == Routine.RESET_ON_COMPLETE:
            s = session if session is not None else self.routine.get_open_session()
            if s is None:
                return False
            return RoutineCompletion.objects.filter(item=self, session=s).exists()
        
        d = for_date or timezone.now().date()
        return RoutineCompletion.objects.filter(item=self, completed_on=d).exists()
    
    def toggle_today(self, for_date=None, session=None):
        """
        Mark complete if not done; undo if already done. Returns new state (bool).
 
        For on_complete routines pass the open session so we don't re-query it.
        After marking complete, auto-closes the session if all items are done.
 
        When marking complete, bulk-dismisses any linked Reminders.
        Does NOT re-activate reminders when toggled off.
        """

        d = for_date or timezone.now().date()

        if self.routine.reset_mode == Routine.RESET_ON_COMPLETE:
            s = session if session is not None else self.routine.get_or_create_session()
            existing = RoutineCompletion.objects.filter(item=self, session=s).first()
            if existing:
                existing.delete()
                return False
            else:
                RoutineCompletion.objects.create(item=self, session=s, completed_on=d)
                # Auto-close session if everything is done now
                s.close_if_complete()
                self.reminders.filter(is_complete=False).update(
                    is_complete=True,
                    is_active=False,
                    completed_at=timezone.now(),
                )
                return True
        else:        
            completion, created = RoutineCompletion.objects.get_or_create(
                item=self, completed_on=d
            )
            if not created:
                completion.delete()
                return False
            
            # Dismiss reminders tied to this specific routine item
            self.reminders.filter(is_complete=False).update(
                is_complete=True,
                is_active=False,
                completed_at=timezone.now(),
            )

            return True
    
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
    """
    Records that a RoutineItem was completed on a specific calendar date.
 
    For daily routines:       session is null; unique_together prevents double-logging.
    For on_complete routines: session is set; uniqueness is enforced in toggle_today().
    """

    item = models.ForeignKey(RoutineItem, on_delete=models.CASCADE, related_name='completions')
    session = models.ForeignKey(
        RoutineSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completions',
        help_text='Set for on_complete routines; null for daily routines.'
    )
    completed_on = models.DateField(default=date.today)
    completed_at = models.DateTimeField(auto_now_add=True)

    
    class Meta:
        unique_together = ('item', 'completed_on')
        ordering = ['-completed_on']
        verbose_name = 'Routine Completion'
        verbose_name_plural = 'Routine Completions'
    
    def __str__(self):
        return f'{self.item} -- {self.completed_on}'


class RoutineSession(models.Model):
    """
    Represents one 'run' of an on_complete Routine. Created lazily when the
    first item is toggled on a scheduled day. Closed automatically when all
    active items have been checked off.
 
    Only used by routines with reset_mode='on_complete'. Daily routines
    never create sessions.
    """

    routine = models.ForeignKey(Routine, on_delete=models.CASCADE, related_name='sessions')
    started_on = models.DateField(default=date.today)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-start_on']
        verbose_name = 'Routine Session'
        verbose_name_plural = 'Routine Sessions'

    def __str__(self):
        status = 'open' if self.completed_at is None else 'done'
        return f'{self.routine.name} — {self.started_on} ({status})'
    

    @property
    def is_open(self):
        return self.completed_at is None
    
    def close_if_complete(self):
        """
        Check whether all active items have a completion in this session.
        If so, stamp completed_at and save. Returns True if just closed.
        """
        items = self.routine.items.filter(is_active=True)
        total = items.count()
        if total == 0:
            return False
        done = RoutineCompletion.objects.filter(
            item__in=items, session=self
        ).count()
        if done >= total and self.completed_at is None:
            self.completed_at = timezone.now()
            self.save(update_fields=['completed_at'])
            return True
        return False
