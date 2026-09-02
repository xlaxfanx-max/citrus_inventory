import django.core.validators
from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lots', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='packout',
            name='bins_packed',
            field=models.DecimalField(
                blank=True,
                decimal_places=1,
                help_text='Bins consumed by this run. Required for an on-hand inventory balance.',
                max_digits=9,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal('0'))],
            ),
        ),
        migrations.AddField(
            model_name='packout',
            name='decay_pct',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Observed decay percent at packout.',
                max_digits=5,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(Decimal('0')),
                    django.core.validators.MaxValueValidator(Decimal('100')),
                ],
            ),
        ),
        migrations.AddField(
            model_name='packout',
            name='downgrade_reason',
            field=models.CharField(
                blank=True,
                help_text='Why fruit went to products (color, decay, size, market, etc.).',
                max_length=200,
            ),
        ),
        migrations.AddField(
            model_name='packout',
            name='is_final',
            field=models.BooleanField(
                default=True,
                help_text='Final packout closes the lot. Clear this for a partial run with fruit remaining.',
            ),
        ),
        migrations.AddField(
            model_name='packout',
            name='packout_color',
            field=models.CharField(
                blank=True,
                choices=[('DG', 'Dark green'), ('LG', 'Light green'), ('S', 'Silver'), ('Y', 'Yellow')],
                help_text='Observed lot color at packout; this is a direct model-validation label.',
                max_length=2,
            ),
        ),
        migrations.AddField(
            model_name='plant',
            name='weekly_pack_capacity_bins',
            field=models.DecimalField(
                blank=True,
                decimal_places=1,
                help_text='Planning capacity in bins per week. Leave blank when not yet known.',
                max_digits=9,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal('0'))],
            ),
        ),
        migrations.AddConstraint(
            model_name='lot',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(('packed_date__isnull', False), ('status', 'packed')),
                    models.Q(('status', 'packed'), _negated=True),
                    _connector='OR',
                ),
                name='packed_lot_has_packed_date',
            ),
        ),
        migrations.AddConstraint(
            model_name='lot',
            constraint=models.CheckConstraint(
                condition=models.Q(('status', 'packed'), ('packed_date__isnull', True), _connector='OR'),
                name='unpacked_lot_has_no_packed_date',
            ),
        ),
        migrations.AddConstraint(
            model_name='lotroommove',
            constraint=models.UniqueConstraint(
                fields=('lot', 'room', 'moved_at'),
                name='unique_room_move_per_lot_day',
            ),
        ),
    ]
