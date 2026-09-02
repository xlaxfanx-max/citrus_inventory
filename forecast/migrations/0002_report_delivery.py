import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('forecast', '0001_initial'),
        ('lots', '0002_inventory_and_integrity'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReportDelivery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('report_date', models.DateField()),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('sent', 'Sent'),
                        ('failed', 'Failed'),
                        ('skipped', 'Skipped'),
                    ],
                    default='pending',
                    max_length=8,
                )),
                ('recipients', models.JSONField(blank=True, default=list)),
                ('subject', models.CharField(blank=True, max_length=250)),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('error', models.TextField(blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('plant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='report_deliveries',
                    to='lots.plant',
                )),
            ],
            options={
                'ordering': ['-report_date', 'plant__code'],
                'constraints': [
                    models.UniqueConstraint(
                        fields=('plant', 'report_date'),
                        name='one_report_delivery_per_plant_date',
                    )
                ],
            },
        ),
    ]
