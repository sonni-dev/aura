import datetime
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('routines', '0001_initial'),
    ]

    operations = [
        # 1. Add reset_mode to Routine
        migrations.AddField(
            model_name='routine',
            name='reset_mode',
            field=models.CharField(
                choices=[
                    ('daily', 'Daily (resets each night)'),
                    ('on_complete', 'On Completion (stays open until all items done)'),
                ],
                default='daily',
                help_text=(
                    'Daily: progress resets each night. '
                    'On Completion: routine stays open on the dashboard until every item is checked off.'
                ),
                max_length=15,
            ),
        ),

        # 2. Create RoutineSession
        migrations.CreateModel(
            name='RoutineSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started_on', models.DateField(default=datetime.date.today)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                (
                    'routine',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='sessions',
                        to='routines.routine',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Routine Session',
                'verbose_name_plural': 'Routine Sessions',
                'ordering': ['-started_on'],
            },
        ),

        # 3. Add nullable session FK to RoutineCompletion
        migrations.AddField(
            model_name='routinecompletion',
            name='session',
            field=models.ForeignKey(
                blank=True,
                help_text='Set for on_complete routines; null for daily routines.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='completions',
                to='routines.routinesession',
            ),
        ),
    ]