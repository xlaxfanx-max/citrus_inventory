import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lots', '0002_inventory_and_integrity'),
        ('sampling', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='sample',
            name='is_void',
            field=models.BooleanField(
                default=False,
                help_text='Voided samples remain in the audit trail but are excluded from forecasts.',
            ),
        ),
        migrations.AddField(
            model_name='sample',
            name='void_reason',
            field=models.CharField(blank=True, max_length=250),
        ),
        migrations.AddField(
            model_name='sample',
            name='voided_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='sample',
            name='voided_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='voided_lemon_samples',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='samplephoto',
            name='attempt_count',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='samplephoto',
            name='processing_started_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='samplephoto',
            name='quality_ok',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='samplephoto',
            name='quality_warnings',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='samplephoto',
            name='scoring_metadata',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Board markers, correction matrix, patch diagnostics and blob centers.',
            ),
        ),
        migrations.AlterField(
            model_name='samplephoto',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('processing', 'Processing'),
                    ('scored', 'Scored'),
                    ('failed', 'Failed'),
                ],
                default='pending',
                max_length=10,
            ),
        ),
        migrations.AddConstraint(
            model_name='sample',
            constraint=models.CheckConstraint(
                condition=models.Q(('decay_count__lte', models.F('fruit_count'))),
                name='sample_decay_not_above_fruit_count',
            ),
        ),
    ]
