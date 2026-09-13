"""Normalize the plant's comma-separated report recipients into their own
table (first normal form) and rename LotRoomMove.moved_at, which is a date,
to moved_on so that the `_at` suffix is reserved for timestamps."""

from django.db import migrations, models
import django.db.models.deletion


def split(text):
    return list(dict.fromkeys(e.strip() for e in (text or '').replace(';', ',').split(',') if e.strip()))


def copy_recipients_forward(apps, schema_editor):
    Plant = apps.get_model('lots', 'Plant')
    PlantReportRecipient = apps.get_model('lots', 'PlantReportRecipient')
    rows = []
    for plant in Plant.objects.all():
        rows.extend(PlantReportRecipient(plant=plant, email=email) for email in split(plant.report_recipients))
    PlantReportRecipient.objects.bulk_create(rows)


def copy_recipients_backward(apps, schema_editor):
    Plant = apps.get_model('lots', 'Plant')
    PlantReportRecipient = apps.get_model('lots', 'PlantReportRecipient')
    for plant in Plant.objects.all():
        plant.report_recipients = ', '.join(
            PlantReportRecipient.objects.filter(plant=plant).order_by('email').values_list('email', flat=True)
        )
        plant.save(update_fields=['report_recipients'])


class Migration(migrations.Migration):

    dependencies = [
        ('lots', '0006_model_settings_sampling_and_temperature'),
    ]

    operations = [
        migrations.RenameField(
            model_name='lotroommove',
            old_name='moved_at',
            new_name='moved_on',
        ),
        migrations.CreateModel(
            name='PlantReportRecipient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254)),
                ('plant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='report_recipients', to='lots.plant')),
            ],
            options={
                'ordering': ['plant__code', 'email'],
                'constraints': [models.UniqueConstraint(fields=('plant', 'email'), name='unique_report_recipient_per_plant')],
            },
        ),
        migrations.RunPython(copy_recipients_forward, copy_recipients_backward),
        migrations.RemoveField(
            model_name='plant',
            name='report_recipients',
        ),
    ]
