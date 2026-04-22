from django.db import migrations, models
 
 
class Migration(migrations.Migration):
 
    dependencies = [
        ('habits', '0001_initial'),
    ]
 
    operations = [
        migrations.AddField(
            model_name='habit',
            name='backfill_days',
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text=(
                    'How many past days the week-dot grid allows logging. '
                    '0 = today only (default). 1 = yesterday + today. '
                    'Set to 1 or 2 for habits like "No Deliveries" that '
                    'can only be confirmed the following day.'
                ),
            ),
        ),
    ]
 