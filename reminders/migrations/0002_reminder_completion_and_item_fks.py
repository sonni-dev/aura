# Generated migration — reminders 0002
# Adds: is_complete, completed_at, goal_item FK, routine_item FK

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('goals',    '0001_initial'),
        ('routines', '0001_initial'),
        ('reminders', '0001_initial'),
    ]

    operations = [
        # ── Completion fields ─────────────────────────────────────────────
        migrations.AddField(
            model_name='reminder',
            name='is_complete',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='reminder',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),

        # ── Item-level source FKs ─────────────────────────────────────────
        migrations.AddField(
            model_name='reminder',
            name='goal_item',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='reminders',
                to='goals.goalitem',
            ),
        ),
        migrations.AddField(
            model_name='reminder',
            name='routine_item',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='reminders',
                to='routines.routineitem',
            ),
        ),
    ]