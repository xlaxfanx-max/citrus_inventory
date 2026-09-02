import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lots', '0002_inventory_and_integrity'),
    ]

    operations = [
        migrations.AddField(
            model_name='importbatch',
            name='plant_scope',
            field=models.ForeignKey(
                blank=True,
                help_text='Plant enforced for a pinned uploader; blank means an authorized multi-plant batch.',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='import_batches',
                to='lots.plant',
            ),
        ),
    ]
