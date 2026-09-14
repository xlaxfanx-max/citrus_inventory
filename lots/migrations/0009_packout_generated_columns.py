"""cartons_total and fresh_pct become STORED generated columns so the
database, not application code, derives them from the carton counts."""

from django.db import migrations, models
from django.db.models import Case, F, Q, Value, When
from django.db.models.functions import Cast, Round


FRESH = F('cartons_fancy') + F('cartons_choice') + F('cartons_standard')
TOTAL = F('cartons_fancy') + F('cartons_choice') + F('cartons_standard') + F('cartons_products')


class Migration(migrations.Migration):

    dependencies = [
        ('lots', '0008_delete_rules_and_constraints'),
    ]

    operations = [
        migrations.RemoveField(model_name='packout', name='cartons_total'),
        migrations.RemoveField(model_name='packout', name='fresh_pct'),
        migrations.AddField(
            model_name='packout',
            name='cartons_total',
            field=models.GeneratedField(
                expression=TOTAL,
                output_field=models.PositiveIntegerField(),
                db_persist=True,
            ),
        ),
        migrations.AddField(
            model_name='packout',
            name='fresh_pct',
            field=models.GeneratedField(
                expression=Case(
                    When(
                        Q(cartons_fancy=0, cartons_choice=0, cartons_standard=0, cartons_products=0),
                        then=Value(None, output_field=models.DecimalField(max_digits=5, decimal_places=2)),
                    ),
                    default=Round(
                        Cast(FRESH, models.FloatField()) * Value(100.0) / Cast(TOTAL, models.FloatField()),
                        2,
                    ),
                    output_field=models.DecimalField(max_digits=5, decimal_places=2),
                ),
                output_field=models.DecimalField(max_digits=5, decimal_places=2, null=True),
                db_persist=True,
            ),
        ),
    ]
